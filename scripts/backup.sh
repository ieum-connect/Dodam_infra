#!/usr/bin/env bash
# [AWS EC2 Ubuntu] Quiesce both writers for a consistent DB/files pair.
set -euo pipefail
umask 077
cd "$(dirname "$0")/.."
dc=(docker compose --env-file "${1:-.env.production}" -f compose.production.yml)
dest="backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$dest"
"${dc[@]}" stop web ai backend
trap '"${dc[@]}" start backend ai web' EXIT
"${dc[@]}" exec -T postgres pg_dump -U dodam -d dodam -Fc > "$dest/database.dump"
"${dc[@]}" run --rm --no-deps --entrypoint tar ai -C /data/object-storage -czf - . > "$dest/uploads.tar.gz"
"${dc[@]}" images --format json > "$dest/images.json"
sha256sum "$dest/database.dump" "$dest/uploads.tar.gz" > "$dest/SHA256SUMS"
echo "Backup complete: $dest. Copy encrypted backup off this server before relying on it."
