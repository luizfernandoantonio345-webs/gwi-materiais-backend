#!/usr/bin/env bash
set -euo pipefail
: "${DATABASE_URL:?defina DATABASE_URL}"
STAMP=$(date +%Y%m%d_%H%M%S)
DEST="${BACKUP_DIR:-./backups}"
mkdir -p "$DEST"
PG_URL=$(echo "$DATABASE_URL" | sed 's/+asyncpg//; s/+psycopg2//')
ARQ="$DEST/gwi_${STAMP}.dump"
echo "Backup -> $ARQ"
pg_dump --format=custom --no-owner --no-privileges --dbname="$PG_URL" --file="$ARQ"
echo "OK ($(du -h "$ARQ" | cut -f1))"
find "$DEST" -name 'gwi_*.dump' -mtime +${RETENTION_DAYS:-14} -delete 2>/dev/null || true
