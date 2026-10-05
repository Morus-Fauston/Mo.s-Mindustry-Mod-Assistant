param([Parameter(Mandatory=$true)][int]$TestProcessId)
$ErrorActionPreference = 'Stop'
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class MoMAWindowClose {
    [DllImport("user32.dll", SetLastError=true)]
    public static extern bool PostMessage(IntPtr handle, uint message, IntPtr wParam, IntPtr lParam);
}
"@
$target = Get-Process -Id $TestProcessId
$target.Refresh()
$handle = $target.MainWindowHandle
if ($handle -eq [IntPtr]::Zero) { throw 'Test host has no native window' }
if (-not [MoMAWindowClose]::PostMessage($handle, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero)) { throw 'Cannot post close to test host' }
Write-Output "Posted WM_CLOSE to test host $TestProcessId"
