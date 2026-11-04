param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

foreach ($envFile in @(".env", ".env.production")) {
    if (-not (Test-Path -LiteralPath $envFile)) {
        continue
    }
    foreach ($line in Get-Content -LiteralPath $envFile) {
        if ($line -notmatch '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') {
            continue
        }
        $name = $matches[1]
        $value = $matches[2].Trim()
        if (
            ($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        Set-Item -Path "Env:$name" -Value $value
    }
}

# Container deployments use /app/frontend/dist. Local ngrok deployments must
# always serve the freshly built workspace bundle instead.
$env:CAREERPILOT_FRONTEND_DIST_PATH = (Resolve-Path -LiteralPath "frontend/dist").Path

& ".venv/Scripts/python.exe" -m uvicorn careerpilot.api.app:app `
    --host 127.0.0.1 `
    --port $Port `
    --proxy-headers `
    --forwarded-allow-ips "127.0.0.1"
exit $LASTEXITCODE
