param(
    [Parameter(Mandatory=$true)][int]$TestProcessId,
    [Parameter(Mandatory=$true)][string]$ExpectedExecutable,
    [Parameter(Mandatory=$true)][string]$ExpectedHostScript,
    [ValidateSet('query','resize')][string]$Action = 'query',
    [int]$OuterWidth = 0,
    [int]$OuterHeight = 0,
    [string]$ExpectedStartTicks = '',
    [string]$ExpectedWindowHandle = ''
)
$ErrorActionPreference = 'Stop'
# Test-only helper. All coordinates are physical pixels in a PMv2 calling thread.
# It never changes global DPI, foreground focus, other windows, or page zoom.
Add-Type @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public static class MoMATestWindowSize {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)] public struct MONITORINFOEX {
        public int cbSize; public RECT Monitor, Work; public uint Flags;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst=32)] public string Device;
    }
    public delegate bool EnumCallback(IntPtr handle, IntPtr parameter);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumCallback callback, IntPtr parameter);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr handle, out uint process);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr handle);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr handle);
    [DllImport("user32.dll")] public static extern bool IsZoomed(IntPtr handle);
    [DllImport("user32.dll")] public static extern IntPtr GetWindow(IntPtr handle, uint command);
    [DllImport("user32.dll", SetLastError=true)] public static extern bool GetWindowRect(IntPtr handle, out RECT rect);
    [DllImport("user32.dll", SetLastError=true)] public static extern bool GetClientRect(IntPtr handle, out RECT rect);
    [DllImport("user32.dll")] public static extern IntPtr MonitorFromWindow(IntPtr handle, uint flags);
    [DllImport("user32.dll", CharSet=CharSet.Unicode, SetLastError=true)] public static extern bool GetMonitorInfo(IntPtr handle, ref MONITORINFOEX info);
    [DllImport("user32.dll")] public static extern uint GetDpiForWindow(IntPtr handle);
    [DllImport("shcore.dll")] public static extern int GetScaleFactorForMonitor(IntPtr handle, out int scale);
    [DllImport("user32.dll", SetLastError=true)] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr context);
    [DllImport("user32.dll", SetLastError=true)] public static extern bool SetWindowPos(IntPtr handle, IntPtr after, int x, int y, int width, int height, uint flags);
    public static IntPtr[] Windows(int process) {
        var handles = new List<IntPtr>();
        EnumCallback callback = (handle, ignored) => {
            uint owner; GetWindowThreadProcessId(handle, out owner);
            if (owner == process && IsWindowVisible(handle) && GetWindow(handle, 4) == IntPtr.Zero) handles.Add(handle);
            return true;
        };
        if (!EnumWindows(callback, IntPtr.Zero)) throw new Exception("Cannot enumerate test windows");
        GC.KeepAlive(callback); return handles.ToArray();
    }
}
"@
function Convert-Rect($rectangle) {
    return @{ left=$rectangle.Left; top=$rectangle.Top; right=$rectangle.Right; bottom=$rectangle.Bottom;
        width=$rectangle.Right-$rectangle.Left; height=$rectangle.Bottom-$rectangle.Top }
}
$target = Get-Process -Id $TestProcessId
$target.Refresh()
$executable = [IO.Path]::GetFullPath($ExpectedExecutable)
if (-not [string]::Equals($target.Path, $executable, [StringComparison]::OrdinalIgnoreCase)) { throw 'PID is not the expected isolated Python executable' }
$processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $TestProcessId"
$script = [IO.Path]::GetFullPath($ExpectedHostScript)
if (-not $processInfo.CommandLine -or $processInfo.CommandLine.Replace('/','\').IndexOf($script, [StringComparison]::OrdinalIgnoreCase) -lt 0) { throw 'PID is not running the expected test-only host script' }
$startTicks = $target.StartTime.ToUniversalTime().Ticks.ToString()
if ($ExpectedStartTicks -and $ExpectedStartTicks -ne $startTicks) { throw 'Test PID was reused' }
$handles = @([MoMATestWindowSize]::Windows($TestProcessId))
if ($handles.Count -ne 1) { throw "Expected exactly one visible owned test window, got $($handles.Count)" }
$handle = $handles[0]
if ($ExpectedWindowHandle -and $ExpectedWindowHandle -ne $handle.ToInt64().ToString()) { throw 'Test window identity changed' }
if ([MoMATestWindowSize]::IsIconic($handle) -or [MoMATestWindowSize]::IsZoomed($handle)) { throw 'Test window must be neither minimized nor maximized' }
$previousDpiContext = [MoMATestWindowSize]::SetThreadDpiAwarenessContext([IntPtr](-4))
if ($previousDpiContext -eq [IntPtr]::Zero) { throw 'Cannot establish physical-pixel PMv2 coordinates' }
try {
    $monitor = [MoMATestWindowSize]::MonitorFromWindow($handle, 2)
    $monitorInfo = New-Object MoMATestWindowSize+MONITORINFOEX
    $monitorInfo.cbSize = [Runtime.InteropServices.Marshal]::SizeOf($monitorInfo)
    if (-not [MoMATestWindowSize]::GetMonitorInfo($monitor, [ref]$monitorInfo)) { throw 'Cannot read test monitor' }
    $scale = 0
    if ([MoMATestWindowSize]::GetScaleFactorForMonitor($monitor, [ref]$scale) -ne 0) { throw 'Cannot read actual monitor scale' }
    $status = 'observed'
    if ($Action -eq 'resize') {
        if ($OuterWidth -lt 100 -or $OuterHeight -lt 100) { throw 'Invalid native outer size' }
        $workWidth = $monitorInfo.Work.Right-$monitorInfo.Work.Left
        $workHeight = $monitorInfo.Work.Bottom-$monitorInfo.Work.Top
        if ($OuterWidth -gt $workWidth -or $OuterHeight -gt $workHeight) {
            $status = 'blocked-work-area'
        } else {
            $target.Refresh()
            [uint32]$ownerId = 0
            [void][MoMATestWindowSize]::GetWindowThreadProcessId($handle, [ref]$ownerId)
            if ($target.HasExited -or $target.StartTime.ToUniversalTime().Ticks.ToString() -ne $startTicks -or $ownerId -ne $TestProcessId) { throw 'Test window owner changed before resize' }
            $x = $monitorInfo.Work.Left + [int][Math]::Floor(($workWidth-$OuterWidth)/2)
            $y = $monitorInfo.Work.Top + [int][Math]::Floor(($workHeight-$OuterHeight)/2)
            # SWP_NOZORDER | SWP_NOACTIVATE; no foreground/window-owner changes.
            if (-not [MoMATestWindowSize]::SetWindowPos($handle, [IntPtr]::Zero, $x, $y, $OuterWidth, $OuterHeight, 0x0014)) { throw 'Native test-window resize failed' }
            $status = 'resized'
        }
    }
    $outer = New-Object MoMATestWindowSize+RECT
    $client = New-Object MoMATestWindowSize+RECT
    if (-not [MoMATestWindowSize]::GetWindowRect($handle, [ref]$outer)) { throw 'Cannot read outer rect' }
    if (-not [MoMATestWindowSize]::GetClientRect($handle, [ref]$client)) { throw 'Cannot read client rect' }
    @{ status=$status; pid=$TestProcessId; startTicks=$startTicks; windowHandle=$handle.ToInt64().ToString();
        executable=$target.Path; commandLine=$processInfo.CommandLine; coordinateSpace='physical-PMv2';
        requestedOuter=@{width=$OuterWidth;height=$OuterHeight}; outer=(Convert-Rect $outer); client=(Convert-Rect $client);
        monitor=@{device=$monitorInfo.Device;scalePercent=$scale;windowDpi=[MoMATestWindowSize]::GetDpiForWindow($handle);
            bounds=(Convert-Rect $monitorInfo.Monitor);work=(Convert-Rect $monitorInfo.Work)} } | ConvertTo-Json -Depth 5 -Compress
} finally {
    [void][MoMATestWindowSize]::SetThreadDpiAwarenessContext($previousDpiContext)
}
