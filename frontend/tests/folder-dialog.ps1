param(
    [Parameter(Mandatory=$true)][int]$TestProcessId,
    [ValidateSet('inspect','select','cancel')][string]$Action = 'inspect',
    [string]$ProjectPath = '',
    [string]$DialogName = '选择文件夹'
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class NativeDialog {
    public delegate bool EnumProc(IntPtr hwnd, IntPtr value);
    [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr parent, EnumProc callback, IntPtr value);
    [DllImport("user32.dll")] public static extern int GetDlgCtrlID(IntPtr hwnd);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr hwnd, StringBuilder text, int count);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr hwnd, StringBuilder text, int count);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr SendMessage(IntPtr hwnd, uint msg, IntPtr value, string text);
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hwnd, uint msg, IntPtr value, IntPtr data);
}
"@
$scope = [System.Windows.Automation.TreeScope]
$element = [System.Windows.Automation.AutomationElement]
$condition = [System.Windows.Automation.PropertyCondition]::new($element::ProcessIdProperty, $TestProcessId)
$deadline = [DateTime]::UtcNow.AddSeconds(15)
$dialog = $null
while (-not $dialog -and [DateTime]::UtcNow -lt $deadline) {
    $windows = $element::RootElement.FindAll($scope::Children, $condition)
    foreach ($window in $windows) {
        $dialogCondition = [System.Windows.Automation.AndCondition]::new(
            [System.Windows.Automation.PropertyCondition]::new($element::ClassNameProperty, '#32770'),
            [System.Windows.Automation.PropertyCondition]::new($element::NameProperty, $DialogName))
        $dialog = $window.FindFirst($scope::Subtree, $dialogCondition)
        if ($dialog) { break }
    }
    if (-not $dialog) { Start-Sleep -Milliseconds 100 }
}
if (-not $dialog) {
    foreach ($window in $windows) {
        Write-Output ($window.Current | Select-Object Name,ClassName,ProcessId,AutomationId | ConvertTo-Json)
        $nested = $window.FindAll($scope::Descendants, [System.Windows.Automation.PropertyCondition]::new($element::ControlTypeProperty, [System.Windows.Automation.ControlType]::Window))
        foreach ($item in $nested) { Write-Output ($item.Current | Select-Object Name,ClassName,ProcessId,AutomationId | ConvertTo-Json) }
    }
    throw '目标宿主未显示原生目录对话框'
}
$all = $dialog.FindAll($scope::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
$details = foreach ($item in $all) {
    [PSCustomObject]@{Name=$item.Current.Name; Id=$item.Current.AutomationId; Type=$item.Current.ControlType.ProgrammaticName}
}
$details | ConvertTo-Json -Depth 3
if ($Action -eq 'inspect') { exit 0 }
$children = [System.Collections.Generic.List[object]]::new()
$callback = [NativeDialog+EnumProc]{ param($handle, $value)
    $class = [System.Text.StringBuilder]::new(256)
    $text = [System.Text.StringBuilder]::new(512)
    [void][NativeDialog]::GetClassName($handle, $class, 256)
    [void][NativeDialog]::GetWindowText($handle, $text, 512)
    $children.Add([PSCustomObject]@{Handle=$handle; Id=[NativeDialog]::GetDlgCtrlID($handle); Class=$class.ToString(); Text=$text.ToString()})
    return $true
}
[void][NativeDialog]::EnumChildWindows([IntPtr]$dialog.Current.NativeWindowHandle, $callback, [IntPtr]::Zero)
if ($Action -eq 'cancel') {
    $button = $children | Where-Object { $_.Id -eq 2 -and $_.Class -eq 'Button' } | Select-Object -First 1
    if (-not $button) { throw '未找到取消按钮' }
    [void][NativeDialog]::PostMessage($button.Handle, 0xF5, [IntPtr]::Zero, [IntPtr]::Zero)
    '已取消原生目录选择'
    exit 0
}
$children | ConvertTo-Json -Depth 3
$inputId = if ($DialogName -eq '打开') { 1148 } else { 1152 }
$target = $children | Where-Object { $_.Class -eq 'Edit' -and $_.Id -eq $inputId } | Select-Object -First 1
if (-not $target) { throw '未找到目录输入框' }
[void][NativeDialog]::SendMessage($target.Handle, 0x0C, [IntPtr]::Zero, $ProjectPath)
$button = $children | Where-Object { $_.Id -eq 1 -and $_.Class -eq 'Button' } | Select-Object -First 1
if (-not $button) { throw '未找到选择目录按钮' }
[void][NativeDialog]::PostMessage($button.Handle, 0xF5, [IntPtr]::Zero, [IntPtr]::Zero)
'已提交原生目录选择'
