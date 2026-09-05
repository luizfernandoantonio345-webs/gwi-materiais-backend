#!/usr/bin/env bash
set -euo pipefail
: "${DATABASE_URL:?defina DATABASE_URL}"
ARQ="${1:?uso: restore.sh <arquivo.dump>}"
PG_URL=$(echo "$DATABASE_URL" | sed 's/+asyncpg//; s/+psycopg2//')
echo "ATENCAO: restaura $ARQ sobre o banco atual. Ctrl-C para abortar."
sleep 3
pg_restore --clean --if-exists --no-owner --no-privileges --dbname="$PG_URL" "$ARQ"
echo "Restore concluido."
