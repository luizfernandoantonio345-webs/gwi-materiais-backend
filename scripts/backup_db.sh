#!/usr/bin/env bash
# Backup do banco Postgres via pg_dump.
# Uso: DATABASE_URL="postgres://user:pass@host:5432/db" ./scripts/backup_db.sh [pasta_destino]
#
# Aceita tanto o formato do Render (postgres://) quanto postgresql://.
# Gera um arquivo comprimido com timestamp e remove backups com mais de 30 dias.

set -euo pipefail

DEST="${1:-backups}"
mkdir -p "$DEST"

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERRO: defina a variável DATABASE_URL (string de conexão do Postgres)." >&2
  exit 1
fi

# pg_dump entende postgres:// e postgresql://; normaliza só por garantia.
URL="${DATABASE_URL/postgresql+asyncpg:\/\//postgresql://}"
URL="${URL/postgres:\/\//postgresql://}"

STAMP="$(date +%Y%m%d_%H%M%S)"
ARQ="$DEST/gwi_materiais_${STAMP}.sql.gz"

echo "Gerando backup em $ARQ ..."
pg_dump "$URL" --no-owner --no-privileges | gzip -9 > "$ARQ"

# Retenção: apaga backups locais com mais de 30 dias.
find "$DEST" -name "gwi_materiais_*.sql.gz" -type f -mtime +30 -delete 2>/dev/null || true

echo "OK: $(du -h "$ARQ" | cut -f1) — $ARQ"
