$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$runtimeDir = Join-Path $projectRoot "data\models"
$pidFile = Join-Path $runtimeDir "embedding-service.pid"
$stdout = Join-Path $runtimeDir "embedding-service-current.log"
$stderr = Join-Path $runtimeDir "embedding-service-current.err.log"

New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
$env:HF_HOME = Join-Path $runtimeDir "huggingface"
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"

try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8001/health" -TimeoutSec 2
    Write-Output "Embedding service is already running: $($health.model)"
    exit 0
} catch {
    # Expected when the service has not started yet.
}

$process = Start-Process `
    -FilePath $python `
    -ArgumentList "scripts\run_embedding_service.py", "--host", "127.0.0.1", "--port", "8001", "--model", "Qwen/Qwen3-Embedding-0.6B", "--device", "cpu", "--batch-size", "8" `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr `
    -PassThru

Set-Content -LiteralPath $pidFile -Value $process.Id -Encoding ascii
Write-Output "Embedding service is starting with launcher PID $($process.Id)."
