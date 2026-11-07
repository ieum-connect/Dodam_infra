# [로컬 Windows PowerShell] Sequential builds; never load production secrets into build args.
param([string]$EnvFile='.env.production.local')
$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot)
docker compose --env-file $EnvFile -f compose.production.yml config --quiet
if ($LASTEXITCODE) { throw 'Compose validation failed' }
foreach ($service in @('backend','ai','web')) {
    docker compose --env-file $EnvFile -f compose.production.yml build $service
    if ($LASTEXITCODE) { throw "Build failed: $service" }
}
