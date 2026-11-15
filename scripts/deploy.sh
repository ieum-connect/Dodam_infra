#!/usr/bin/env bash
# [AWS EC2 Ubuntu] Deploy previously loaded immutable images; no server builds.
set -euo pipefail
cd "$(dirname "$0")/.."
env_file=${1:-.env.production}
chmod 600 "$env_file"
python3 scripts/configure.py "$env_file"
dc=(docker compose --env-file "$env_file" -f compose.production.yml)
"${dc[@]}" config --quiet
# The release archive excludes secrets. A fresh install still needs the default bind source.
mkdir -p secrets/firebase
"${dc[@]}" up -d --no-build --wait --wait-timeout 240
"${dc[@]}" exec -T web nginx -t
"${dc[@]}" exec -T web nginx -s reload
bash scripts/status.sh "$env_file"
