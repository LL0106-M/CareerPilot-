$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pidFile = Join-Path $projectRoot "data\models\embedding-service.pid"
if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Output "Embedding service PID file does not exist."
    exit 0
}

$servicePid = [int](Get-Content -LiteralPath $pidFile -Raw)
taskkill /PID $servicePid /T /F | Out-Null
Remove-Item -LiteralPath $pidFile -Force
Write-Output "Embedding service process tree stopped."
