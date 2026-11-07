#!/usr/bin/env bash
# Read-only checks on the target EC2. No app requests or paid model calls.
set -euo pipefail
command -v curl >/dev/null || { echo 'curl is required'; exit 1; }
token=$(curl --noproxy '*' -fsS --connect-timeout 2 --max-time 5 -X PUT \
  -H 'X-aws-ec2-metadata-token-ttl-seconds: 60' http://169.254.169.254/latest/api/token)
region=$(curl --noproxy '*' -fsS --connect-timeout 2 --max-time 5 \
  -H "X-aws-ec2-metadata-token: $token" http://169.254.169.254/latest/meta-data/placement/region)
unset token
[[ $region == ap-southeast-2 ]] || { echo 'Wrong region: expected ap-southeast-2'; exit 1; }
[[ $(uname -m) == x86_64 ]] || { echo 'Current release requires x86_64/amd64'; exit 1; }
. /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 24.04 ]] || { echo 'This runbook targets Ubuntu 24.04'; exit 1; }
echo 'PASS: Sydney, x86_64, Ubuntu 24.04'
free -h
df -h / /opt
if command -v docker >/dev/null; then
  docker version --format '{{.Server.Version}}'
  docker compose version
else
  echo 'NEXT: install Docker using README section 4'
fi
echo 'This checks host prerequisites only, not successful deployment.'
