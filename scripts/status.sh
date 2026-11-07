#!/usr/bin/env bash
# [AWS EC2 Ubuntu]
set -euo pipefail
cd "$(dirname "$0")/.."
dc=(docker compose --env-file "${1:-.env.production}" -f compose.production.yml)
"${dc[@]}" ps
"${dc[@]}" exec -T postgres psql -U dodam -d dodam -c 'SELECT version FROM flyway_schema_history ORDER BY installed_rank DESC LIMIT 1;'
"${dc[@]}" exec -T backend curl -fsS http://localhost:8081/api/auth/config
"${dc[@]}" exec -T ai python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8006/health').status)"
"${dc[@]}" exec -T web nginx -t
