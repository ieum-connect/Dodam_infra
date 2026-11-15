# [로컬 Windows PowerShell]
param([string]$EnvFile='.env.production.local')
$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot)
$values=@{}
Get-Content $EnvFile | ForEach-Object { if ($_ -match '^([^#=]+)=(.*)$') {$values[$matches[1]]=$matches[2]} }
$tag=$values['RELEASE_TAG']
if ($tag -notmatch '^[a-zA-Z0-9][a-zA-Z0-9_.-]+$') {throw 'Invalid release tag'}
$images=@(docker compose --env-file $EnvFile -f compose.production.yml --profile tools config --images)
if ($LASTEXITCODE -or !$images.Count) {throw 'Could not resolve release images from Compose'}
$dest=Join-Path $PWD "releases/$tag"
New-Item -ItemType Directory -Force $dest | Out-Null
docker pull certbot/certbot:v5.9.0
if ($LASTEXITCODE) {throw 'Certificate image pull failed'}
docker image save -o "$dest/images.tar" @images
if ($LASTEXITCODE) {throw 'Image export failed'}
$versions=@{created=(Get-Date).ToUniversalTime().ToString('o'); tag=$tag; sources=@{}}
foreach ($repo in @('frontend','backend','ai-backend')) {
    $source=Join-Path $values['SOURCE_ROOT'] $repo
    $dirty=git -C $source status --porcelain
    if ($dirty) {throw "Source $repo is dirty; do not publish this bundle"}
    $versions.sources[$repo]=(git -C $source rev-parse HEAD)
}
$versions.infra=(git rev-parse HEAD)
$versions.images=(docker image inspect @images --format '{{.RepoTags}} {{.Id}}')
$versions | ConvertTo-Json -Depth 5 | Set-Content "$dest/versions.json" -Encoding utf8
Get-FileHash "$dest/images.tar" -Algorithm SHA256 | Select-Object Hash | ConvertTo-Json | Set-Content "$dest/checksum.json"
tar -czf "$dest/infra.tar.gz" --exclude=.git --exclude=.env.production.local --exclude=.env.production --exclude=backups --exclude=releases --exclude=verification --exclude=active --exclude=__pycache__ --exclude='*.log' compose.production.yml .env.production.example .gitignore .gitattributes docker nginx postgres scripts README.md AUDIT.md RESULTS.md DEPLOYMENT_GUIDE.md EC2_SYDNEY.md 도담_배포_가이드라인.html
if ($LASTEXITCODE) {throw 'Configuration export failed'}
Write-Output "Release created: $dest (no environment secrets included)"
