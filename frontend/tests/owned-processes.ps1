param(
    [ValidateSet('sample','check','terminate')][string]$Action = 'check',
    [int]$RootProcessId = 0,
    [string]$KnownJson = '[]'
)
$ErrorActionPreference = 'Stop'
# Only records created by this fixture may be checked/terminated. Creation time
# prevents a reused PID from being treated as the previous test process.
$decoded = ConvertFrom-Json -InputObject $KnownJson
# Windows PowerShell 5.1 emits an array as one pipeline value here. Wrapping the
# command directly in @() turns [] into one nested empty array (and pid into 0).
$known = @($decoded)
foreach ($record in $known) {
    if ($null -eq $record -or [int]$record.pid -le 0 -or [string]$record.createdTicks -notmatch '^\d+$') {
        throw 'Invalid saved process identity; refusing PID 0 or missing creation time'
    }
}
function Read-Identity([int]$ProcessId) {
    if ($ProcessId -le 0) { throw 'Process identity must have a positive PID' }
    try {
        $process = Get-Process -Id $ProcessId -ErrorAction Stop
        $started = $process.StartTime
        if ($null -eq $started) {
            if ($process.HasExited) { return $null }
            throw 'Cannot verify creation time for live owned process'
        }
        return @{ pid=$process.Id; createdTicks=$started.ToUniversalTime().Ticks.ToString(); name=$process.ProcessName }
    } catch [Microsoft.PowerShell.Commands.ProcessCommandException] { return $null }
}
$matching = @()
$reused = @()
foreach ($record in $known) {
    $current = Read-Identity ([int]$record.pid)
    if ($current) {
        if ($current.createdTicks -eq [string]$record.createdTicks) { $matching += $current }
        else { $reused += $current }
    }
}
if ($Action -eq 'sample') {
    $all = @(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,CreationDate)
    $ids = [System.Collections.Generic.HashSet[int]]::new()
    $found = @($matching)
    foreach ($record in $matching) { [void]$ids.Add([int]$record.pid) }
    # RootProcessId is only supplied once, directly from Node spawn().pid.
    if ($RootProcessId -gt 0) {
        $current = Read-Identity $RootProcessId
        if ($current -and $ids.Add($RootProcessId)) { $found += $current }
    }
    do {
        $added = $false
        foreach ($row in $all) {
            if (-not $ids.Contains([int]$row.ParentProcessId) -or $ids.Contains([int]$row.ProcessId)) { continue }
            $parent = $found | Where-Object { $_.pid -eq [int]$row.ParentProcessId } | Select-Object -First 1
            $childIdentity = Read-Identity ([int]$row.ProcessId)
            if (-not $childIdentity) { continue }
            # Reject stale ParentProcessId links to a newer/reused parent PID.
            if ([long]$childIdentity.createdTicks -lt [long]$parent.createdTicks) { continue }
            # CIM serializes creation times at microsecond precision; retain the
            # exact Process.StartTime ticks for later identity checks.
            if ([Math]::Abs($row.CreationDate.ToUniversalTime().Ticks - [long]$childIdentity.createdTicks) -ge 10) { continue }
            if ($ids.Add([int]$row.ProcessId)) { $found += $childIdentity; $added = $true }
        }
    } while ($added)
    @{ action=$Action; identities=@($found); reused=@($reused); sampledUtc=[DateTime]::UtcNow.ToString('o') } | ConvertTo-Json -Compress -Depth 4
    exit 0
}
if ($Action -eq 'terminate') {
    foreach ($record in $matching) {
        try {
            $process = Get-Process -Id ([int]$record.pid) -ErrorAction Stop
            # Force handle acquisition before checking StartTime and killing this
            # same process object. No taskkill /IM or global browser enumeration.
            $null = $process.Handle
            if ($process.HasExited) { continue }
            $started = $process.StartTime
            if ($null -eq $started) {
                if ($process.HasExited) { continue }
                throw 'Cannot verify creation time before terminating live owned process'
            }
            if ($started.ToUniversalTime().Ticks.ToString() -eq [string]$record.createdTicks) { $process.Kill() }
        } catch [Microsoft.PowerShell.Commands.ProcessCommandException] { }
    }
}
$survivors = @()
foreach ($record in $known) {
    $current = Read-Identity ([int]$record.pid)
    if ($current -and $current.createdTicks -eq [string]$record.createdTicks) { $survivors += $current }
}
@{ action=$Action; survivors=@($survivors); reused=@($reused); sampledUtc=[DateTime]::UtcNow.ToString('o') } | ConvertTo-Json -Compress -Depth 4
