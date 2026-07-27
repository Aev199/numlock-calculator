param(
    [Parameter(Mandatory = $true)]
    [string]$TargetPath
)

$ErrorActionPreference = 'Stop'

# A one-file PyInstaller build can leave both its parent bootloader process and
# the child application process alive. Stop every process with the current or
# legacy executable name before replacing the previous build output.
Get-Process -Name 'NumCalc', 'NumLockCalc' -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue

$resolvedTarget = Join-Path (Get-Location) $TargetPath
$deadline = (Get-Date).AddSeconds(8)

while ($true) {
    try {
        if (Test-Path -LiteralPath $resolvedTarget) {
            Remove-Item -LiteralPath $resolvedTarget -Recurse -Force -ErrorAction Stop
        }
        exit 0
    }
    catch {
        if ((Get-Date) -ge $deadline) {
            Write-Error "Cannot release previous build output: $resolvedTarget. Close NumCalc.exe and try again. $($_.Exception.Message)"
            exit 1
        }
        Start-Sleep -Milliseconds 200
    }
}
