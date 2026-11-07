#!/usr/bin/env bash
# [AWS EC2 Ubuntu] Schedule twice daily as a systemd timer/cron with restricted logs.
set -euo pipefail
cd "$(dirname "$0")/.."
dc=(docker compose --env-file "${1:-.env.production}" -f compose.production.yml)
"${dc[@]}" run --rm certbot renew --webroot -w /var/www/acme --quiet
"${dc[@]}" exec -T web nginx -t
"${dc[@]}" exec -T web nginx -s reload
