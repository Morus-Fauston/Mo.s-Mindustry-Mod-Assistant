param([Parameter(Mandatory=$true)][string]$RequestPath)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$request = Get-Content -LiteralPath $RequestPath -Raw -Encoding UTF8 | ConvertFrom-Json
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName WindowsBase
Add-Type -AssemblyName System.Windows.Forms
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class PackageNative {
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr window);
    [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr window);
    [DllImport("user32.dll", SetLastError=true)] public static extern bool AttachThreadInput(uint from, uint to, bool attach);
    [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr window, out uint process);
    [DllImport("user32.dll")] public static extern IntPtr GetAncestor(IntPtr window, uint flags);
    [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr context);
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int x, y; public POINT(int x, int y) { this.x=x; this.y=y; } }
    [DllImport("user32.dll")] public static extern IntPtr WindowFromPoint(POINT point);
    [DllImport("user32.dll", SetLastError=true)] public static extern bool SetCursorPos(int x, int y);
    [StructLayout(LayoutKind.Sequential)] public struct KEYBDINPUT { public ushort vk, scan; public uint flags, time; public UIntPtr extra; }
    [StructLayout(LayoutKind.Sequential)] public struct MOUSEINPUT { public int x, y; public uint data, flags, time; public UIntPtr extra; }
    [StructLayout(LayoutKind.Explicit)] public struct UNION { [FieldOffset(0)] public KEYBDINPUT keyboard; [FieldOffset(0)] public MOUSEINPUT mouse; }
    [StructLayout(LayoutKind.Sequential)] public struct INPUT { public uint type; public UNION input; }
    [DllImport("user32.dll", SetLastError=true)] public static extern uint SendInput(uint count, INPUT[] input, int size);
    public static void Click() {
        var input = new INPUT[2];
        input[0].input.mouse.flags = 2; input[1].input.mouse.flags = 4;
        if (SendInput(2, input, Marshal.SizeOf(typeof(INPUT))) != 2)
            throw new InvalidOperationException("Native mouse click was not fully delivered");
    }
}
'@
# UIA bounds and native hit-testing must use the same physical pixel coordinates.
if ([PackageNative]::SetThreadDpiAwarenessContext([IntPtr](-4)) -eq [IntPtr]::Zero) { throw '无法进入每显示器DPI坐标上下文' }
$scope = [System.Windows.Automation.TreeScope]
$element = [System.Windows.Automation.AutomationElement]
$deadline = [DateTime]::UtcNow.AddMilliseconds([Math]::Min(15000, [int]$request.timeoutMs))
$script:foregroundAcquisition = $null
function Assert-Owned([int]$ProcessId) {
    $saved = @($request.identities | Where-Object { [int]$_.pid -eq $ProcessId })
    if ($saved.Count -ne 1 -or $ProcessId -le 0) {
        $name = if ($ProcessId -gt 0) { (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue).ProcessName } else { $null }
        throw ('目标不属于本次记录的进程树：' + (@{ receivedPid=$ProcessId; receivedName=$name;
            expectedIdentities=@($request.identities); foregroundAcquisition=$script:foregroundAcquisition } | ConvertTo-Json -Depth 7 -Compress))
    }
    $process = Get-Process -Id $ProcessId -ErrorAction Stop
    if ($process.StartTime.ToUniversalTime().Ticks.ToString() -ne [string]$saved[0].createdTicks) {
        throw ('目标 PID 已复用：' + (@{ receivedPid=$ProcessId; receivedName=$process.ProcessName;
            actualCreatedTicks=$process.StartTime.ToUniversalTime().Ticks.ToString(); expectedIdentity=$saved[0] } | ConvertTo-Json -Depth 5 -Compress))
    }
}
function Windows {
    $result = @()
    foreach ($record in @($request.identities)) {
        try { Assert-Owned ([int]$record.pid) } catch [Microsoft.PowerShell.Commands.ProcessCommandException] { continue }
        $condition = [System.Windows.Automation.PropertyCondition]::new($element::ProcessIdProperty, [int]$record.pid)
        foreach ($window in $element::RootElement.FindAll($scope::Children, $condition)) {
            if ($window.Current.Name -eq 'MoMA' -or $window.Current.Name -like 'MoMA *') { $result += $window }
        }
    }
    return $result
}
function Describe($item) {
    $pattern = $null
    $value = $null
    if ($item.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$pattern)) { $value = $pattern.Current.Value }
    return @{ name=$item.Current.Name; type=$item.Current.ControlType.ProgrammaticName; pid=$item.Current.ProcessId;
        enabled=$item.Current.IsEnabled; offscreen=$item.Current.IsOffscreen; value=$value }
}
function Read-InputText($item) {
    $pattern = $null
    if ($item.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$pattern)) {
        return @{ value=[string]$pattern.Current.Value; pattern='ValuePattern' }
    }
    if ($item.TryGetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern, [ref]$pattern)) {
        # Single-line input only; Chromium may append a document-ending newline.
        return @{ value=([string]$pattern.DocumentRange.GetText(-1)).TrimEnd([char[]]"`r`n"); pattern='TextPattern' }
    }
    throw '目标没有可独立读回的 ValuePattern 或 TextPattern，不能确认原生输入'
}
function Keep-InputSenderAlive {
    # Give the receiver a bounded consumption opportunity for the one mouse click.
    # Pump only; never replay the click or declare it a business success.
    # This is not a business-success wait and shares the original deadline.
    $until = [DateTime]::UtcNow.AddMilliseconds(400)
    do {
        if ([DateTime]::UtcNow -ge $deadline) { throw '等待原生输入消费机会时已达原操作截止时间' }
        [System.Windows.Forms.Application]::DoEvents()
        $left = ($until - [DateTime]::UtcNow).TotalMilliseconds
        if ($left -gt 0) { Start-Sleep -Milliseconds ([Math]::Min(10, [int][Math]::Ceiling($left))) }
    } while ([DateTime]::UtcNow -lt $until)
    if ([DateTime]::UtcNow -ge $deadline) { throw '原生输入发送者保活超出原操作截止时间' }
}
function Assert-Foreground($window) {
    Assert-Owned $window.Current.ProcessId
    $expected = [IntPtr]$window.Current.NativeWindowHandle
    $foreground = [PackageNative]::GetForegroundWindow()
    $foregroundPid = [uint32]0
    [void][PackageNative]::GetWindowThreadProcessId($foreground, [ref]$foregroundPid)
    Assert-Owned ([int]$foregroundPid)
    if ($expected -eq [IntPtr]::Zero -or [PackageNative]::GetAncestor($foreground, 2) -ne [PackageNative]::GetAncestor($expected, 2)) {
        throw ('前台窗口不是本次唯一MoMA主窗口，拒绝输入：' + (@{ expectedHwnd=$expected.ToInt64(); foregroundHwnd=$foreground.ToInt64();
            foregroundPid=$foregroundPid; acquisition=$script:foregroundAcquisition } | ConvertTo-Json -Depth 7 -Compress))
    }
}
function Acquire-Foreground($window) {
    Assert-Owned $window.Current.ProcessId
    $expected = [IntPtr]$window.Current.NativeWindowHandle
    if ($expected -eq [IntPtr]::Zero) { throw '目标主窗口没有原生句柄' }
    $targetPid = [uint32]0
    $targetThread = [PackageNative]::GetWindowThreadProcessId($expected, [ref]$targetPid)
    Assert-Owned ([int]$targetPid)
    $before = [PackageNative]::GetForegroundWindow()
    $beforePid = [uint32]0
    $beforeThread = [PackageNative]::GetWindowThreadProcessId($before, [ref]$beforePid)
    $callerThread = [PackageNative]::GetCurrentThreadId()
    $script:foregroundAcquisition = @{ targetHwnd=$expected.ToInt64(); targetPid=$targetPid; targetThread=$targetThread;
        beforeHwnd=$before.ToInt64(); beforePid=$beforePid; beforeThread=$beforeThread; callerThread=$callerThread;
        attachments=@(); setForeground=$null; bringToTop=$null; detached=@() }
    if ([PackageNative]::GetAncestor($before, 2) -eq [PackageNative]::GetAncestor($expected, 2)) {
        Assert-Foreground $window
        $script:foregroundAcquisition.alreadyForeground=$true
        $script:foregroundAcquisition.afterHwnd=$before.ToInt64()
        return $script:foregroundAcquisition
    }
    # Normal activation comes first. An unrelated foreground process (for example
    # a tablet driver) is not an input-queue attachment prerequisite or target.
    if ([DateTime]::UtcNow -ge $deadline) { throw '正常前台激活前已达原操作截止时间' }
    $script:foregroundAcquisition.directBringToTop = [PackageNative]::BringWindowToTop($expected)
    $script:foregroundAcquisition.directSetForeground = [PackageNative]::SetForegroundWindow($expected)
    $normalDeadline = [DateTime]::UtcNow.AddMilliseconds(500)
    if ($normalDeadline -gt $deadline) { $normalDeadline = $deadline }
    while ([DateTime]::UtcNow -lt $normalDeadline) {
        Assert-Owned ([int]$targetPid)
        $current = [PackageNative]::GetForegroundWindow()
        if ([PackageNative]::GetAncestor($current, 2) -eq [PackageNative]::GetAncestor($expected, 2)) {
            Assert-Foreground $window
            $script:foregroundAcquisition.afterHwnd=$current.ToInt64()
            $script:foregroundAcquisition.method='normal'
            return $script:foregroundAcquisition
        }
        Start-Sleep -Milliseconds 50
    }
    if ([DateTime]::UtcNow -ge $deadline) {
        throw ('正常激活后已达原操作截止时间：' + ($script:foregroundAcquisition | ConvertTo-Json -Depth 6 -Compress))
    }
    $attached = [System.Collections.Generic.List[uint32]]::new()
    $acquireError = $null
    try {
        # Only the verified target thread may be associated with this caller.
        # Never attach to the unrelated process that currently owns foreground.
        $fallbackPid = [uint32]0
        $fallbackThread = [PackageNative]::GetWindowThreadProcessId($expected, [ref]$fallbackPid)
        Assert-Owned ([int]$fallbackPid)
        if ($fallbackPid -ne $targetPid -or $fallbackThread -ne $targetThread) { throw '目标窗口在线程关联前已更换身份' }
        foreach ($thread in @($targetThread)) {
            if ($thread -eq 0 -or $thread -eq $callerThread) { continue }
            $ok = [PackageNative]::AttachThreadInput($callerThread, $thread, $true)
            $script:foregroundAcquisition.attachments += @{ thread=$thread; succeeded=$ok; error=[System.Runtime.InteropServices.Marshal]::GetLastWin32Error() }
            if (-not $ok) { throw '无法临时关联已验证目标输入线程' }
            $attached.Add($thread)
        }
        $script:foregroundAcquisition.bringToTop = [PackageNative]::BringWindowToTop($expected)
        $script:foregroundAcquisition.setForeground = [PackageNative]::SetForegroundWindow($expected)
    } catch { $acquireError = $_.Exception.Message } finally {
        # Even a failed acquisition must not leave input queues associated.
        for ($index = $attached.Count - 1; $index -ge 0; $index--) {
            $thread = $attached[$index]
            $ok = [PackageNative]::AttachThreadInput($callerThread, $thread, $false)
            $script:foregroundAcquisition.detached += @{ thread=$thread; succeeded=$ok; error=[System.Runtime.InteropServices.Marshal]::GetLastWin32Error() }
        }
    }
    if (@($script:foregroundAcquisition.detached | Where-Object { -not $_.succeeded }).Count) {
        throw ('解除临时输入线程关联失败：' + ($script:foregroundAcquisition | ConvertTo-Json -Depth 6 -Compress))
    }
    if ($acquireError) {
        throw ($acquireError + '：' + ($script:foregroundAcquisition | ConvertTo-Json -Depth 6 -Compress))
    }
    while ([DateTime]::UtcNow -lt $deadline) {
        Assert-Owned ([int]$targetPid)
        $current = [PackageNative]::GetForegroundWindow()
        if ([PackageNative]::GetAncestor($current, 2) -eq [PackageNative]::GetAncestor($expected, 2)) {
            Assert-Foreground $window
            $script:foregroundAcquisition.afterHwnd=$current.ToInt64()
            $script:foregroundAcquisition.method='target-thread-only'
            return $script:foregroundAcquisition
        }
        Start-Sleep -Milliseconds 50
    }
    $script:foregroundAcquisition.afterHwnd=[PackageNative]::GetForegroundWindow().ToInt64()
    throw ('原截止前未取得准确主窗口前台：' + ($script:foregroundAcquisition | ConvertTo-Json -Depth 6 -Compress))
}
function Focus-Owned($item, $window) {
    Assert-Owned $window.Current.ProcessId
    $null = Acquire-Foreground $window
    $expectedFocus = Describe $item
    $item.SetFocus()
    # UIA focus changes cross the host/renderer boundary asynchronously. Request
    # focus once, then observe it within the original budget without sending input.
    $actualFocus = $null
    while ([DateTime]::UtcNow -lt $deadline) {
        Assert-Foreground $window
        $actualFocus = $element::FocusedElement
        if ([System.Windows.Automation.Automation]::Compare($actualFocus, $item)) { return }
        Start-Sleep -Milliseconds 50
    }
    $actualDescription = $null
    try { if ($actualFocus) { $actualDescription = Describe $actualFocus } } catch { $actualDescription = @{ unavailable=$_.Exception.Message } }
    throw ('原操作截止前焦点未到目标，拒绝操作：' + (@{ expected=$expectedFocus; actual=$actualDescription;
        foregroundHwnd=[PackageNative]::GetForegroundWindow().ToInt64(); deadlineUtc=$deadline.ToString('o') } | ConvertTo-Json -Depth 5 -Compress))
}
function Click-Owned($item, $window) {
    Assert-Owned $item.Current.ProcessId
    $acquisition = Acquire-Foreground $window
    Assert-Foreground $window
    $bounds = $item.Current.BoundingRectangle
    $click = $item.GetClickablePoint()
    $x = [int][Math]::Round($click.X); $y = [int][Math]::Round($click.Y)
    if ($bounds.IsEmpty -or $bounds.Width -le 0 -or $bounds.Height -le 0 -or
        $x -lt $bounds.Left -or $x -ge $bounds.Right -or $y -lt $bounds.Top -or $y -ge $bounds.Bottom) { throw 'UIA点击点不在目标物理边界内' }
    if (-not [PackageNative]::SetCursorPos($x, $y)) { throw '原生鼠标无法移动到目标点击点' }
    $hitWindow = [PackageNative]::WindowFromPoint([PackageNative+POINT]::new($x, $y))
    $hitPid = [uint32]0
    [void][PackageNative]::GetWindowThreadProcessId($hitWindow, [ref]$hitPid)
    Assert-Owned ([int]$hitPid)
    if ([PackageNative]::GetAncestor($hitWindow, 2) -ne [PackageNative]::GetAncestor([IntPtr]$window.Current.NativeWindowHandle, 2)) { throw '点击点原生窗口不属于目标主窗口' }
    $hit = $element::FromPoint([System.Windows.Point]::new($x, $y))
    $candidate = $hit; $inside = $false
    for ($depth = 0; $candidate -and $depth -lt 20; $depth++) {
        if ([System.Windows.Automation.Automation]::Compare($candidate, $item)) { $inside = $true; break }
        $candidate = [System.Windows.Automation.TreeWalker]::RawViewWalker.GetParent($candidate)
    }
    if (-not $inside) { throw 'UIA点击点命中了其他控件，拒绝点击' }
    $evidence = @{ bounds=@{ x=$bounds.X; y=$bounds.Y; width=$bounds.Width; height=$bounds.Height };
        point=@{ x=$x; y=$y }; hit=(Describe $hit); hitHwnd=$hitWindow.ToInt64(); foregroundHwnd=[PackageNative]::GetForegroundWindow().ToInt64(); acquisition=$acquisition }
    Assert-Foreground $window
    if (-not $item.Current.IsEnabled) { throw '目标点击前已禁用' }
    [PackageNative]::Click()
    Keep-InputSenderAlive
    return $evidence
}
$windows = @()
$matches = @()
do {
    $windows = @(Windows)
    if ($request.action -in @('dump','close','dialog')) { if ($windows.Count -eq 1) { break } }
    else {
        $matches = @()
        foreach ($window in $windows) {
            $condition = [System.Windows.Automation.PropertyCondition]::new($element::NameProperty, [string]$request.name)
            foreach ($item in $window.FindAll($scope::Descendants, $condition)) {
                if ($item.Current.IsOffscreen -and $request.action -ne 'reveal') { continue }
                if ($request.type -and $item.Current.ControlType.ProgrammaticName -ne ('ControlType.' + $request.type)) { continue }
                $matches += $item
            }
        }
        if ($matches.Count -gt 1) { throw ('控件匹配不唯一：' + $request.name + '，' + $matches.Count) }
        if ($matches.Count -eq 1 -and ($request.action -eq 'read' -or $matches[0].Current.IsEnabled)) { break }
    }
    Start-Sleep -Milliseconds 150
} while ([DateTime]::UtcNow -lt $deadline)
if ($windows.Count -ne 1) { throw ('本次进程树内主窗口数应为 1，实际：' + $windows.Count) }
$window = $windows[0]
Assert-Owned $window.Current.ProcessId
if ($request.action -eq 'dump') {
    $rows = foreach ($item in $window.FindAll($scope::Descendants, [System.Windows.Automation.Condition]::TrueCondition)) { Describe $item }
    @{ window=(Describe $window); elements=@($rows) } | ConvertTo-Json -Depth 6 -Compress
    exit 0
}
if ($request.action -eq 'dialog') {
    & "$PSScriptRoot/folder-dialog.ps1" -TestProcessId $window.Current.ProcessId -Action select -ProjectPath $request.value -DialogName $request.name
    exit 0
}
if ($request.action -eq 'close') {
    & "$PSScriptRoot/window-close.ps1" -TestProcessId $window.Current.ProcessId
    exit 0
}
if ($matches.Count -ne 1) { throw ('未找到唯一可见控件：' + $request.name) }
$target = $matches[0]
if ($request.action -eq 'click') {
    if ($target.Current.ControlType.ProgrammaticName -notin @('ControlType.Button', 'ControlType.MenuItem', 'ControlType.TreeItem')) {
        throw '该控件类别尚未定义原生鼠标激活契约'
    }
    $before = Describe $target
    $click = Click-Owned $target $window
    # Do not read an element that the successful click may already have removed.
    # The caller must independently assert the resulting workspace state.
    @{ action=$request.action; target=$before; clickEvidence=$click;
        resultConfirmed=$false; utc=[DateTime]::UtcNow.ToString('o') } | ConvertTo-Json -Depth 6 -Compress
    exit 0
} elseif ($request.action -eq 'reveal') {
    # UIA focus/ScrollItemPattern asks the actual host to reveal its own control.
    $pattern = $null
    if ($target.TryGetCurrentPattern([System.Windows.Automation.ScrollItemPattern]::Pattern, [ref]$pattern)) { $pattern.ScrollIntoView() }
    Focus-Owned $target $window
} elseif ($request.action -eq 'expandTree') {
    $expanded = 0
    do {
        $collapsed = $null
        $treeItems = $target.FindAll($scope::Descendants, [System.Windows.Automation.PropertyCondition]::new($element::ControlTypeProperty, [System.Windows.Automation.ControlType]::TreeItem))
        foreach ($item in $treeItems) {
            $pattern = $null
            if (-not $item.Current.IsOffscreen -and $item.TryGetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern, [ref]$pattern) -and $pattern.Current.ExpandCollapseState -eq [System.Windows.Automation.ExpandCollapseState]::Collapsed) {
                $collapsed = $item; break
            }
        }
        if ($collapsed) {
            Assert-Owned $window.Current.ProcessId
            $pattern.Expand(); $expanded++
            Start-Sleep -Milliseconds 150
        }
        if ($expanded -gt 80 -or [DateTime]::UtcNow -ge $deadline) { throw '展开本次工程树超过节点数或时间预算' }
    } while ($collapsed)
 } elseif ($request.action -in @('setValue', 'setNumericValue')) {
    $text = [string]$request.value
    if (-not $text -or $text.Length -gt 10000 -or $text -match '[\x00-\x1f]') { throw 'UIA填值仅允许有界单行文本' }
    if ($request.action -eq 'setNumericValue' -and $text -notmatch '^-?\d+(\.\d+)?$') { throw '数值输入参数无效' }
    Focus-Owned $target $window
    $writer = $null
    if (-not $target.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$writer) -or $writer.Current.IsReadOnly) {
        throw '控件没有可写ValuePattern；本驱动不降级为其他输入方式'
    }
    $writer.SetValue($text)
    $observed = $null
    do {
        $observed = Read-InputText $target
        if ($observed.value -ceq $text) { break }
        Start-Sleep -Milliseconds 50
    } while ([DateTime]::UtcNow -lt $deadline)
    if ($observed.value -cne $text) { throw ('UIA SetValue未完整读回：' + (@{ expected=$text; observed=$observed } | ConvertTo-Json -Compress)) }
    $blur = $null
    if ($request.action -eq 'setNumericValue') {
        # A real focus transition triggers the form's blur commit without keyboard
        # injection. The header File button is persistent and is not activated.
        $buttons = @($window.FindAll($scope::Descendants, [System.Windows.Automation.PropertyCondition]::new($element::NameProperty, '文件')) | Where-Object {
            $_.Current.ControlType.ProgrammaticName -eq 'ControlType.Button' -and -not $_.Current.IsOffscreen -and $_.Current.IsEnabled
        })
        if ($buttons.Count -ne 1) { throw '无法唯一定位用于失焦提交的文件按钮' }
        Focus-Owned $buttons[0] $window
        $blur = Describe $element::FocusedElement
        $observed = Read-InputText $target
        if ($observed.value -cne $text) { throw '失焦后数值被回退，UIA填值未进入表单状态' }
    }
    @{ action=$request.action; target=(Describe $target); verifiedText=$observed;
        blurTarget=$blur; inputMethod='ValuePattern.SetValue'; resultConfirmed=$false; utc=[DateTime]::UtcNow.ToString('o') } | ConvertTo-Json -Depth 5 -Compress
    exit 0
} elseif ($request.action -ne 'read') { throw '未知原生操作' }
@{ action=$request.action; target=(Describe $target); utc=[DateTime]::UtcNow.ToString('o') } | ConvertTo-Json -Depth 5 -Compress
