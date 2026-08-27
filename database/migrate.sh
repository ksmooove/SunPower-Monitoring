#!/bin/sh
set -eu
echo "Applying migrations..."
for f in $(ls -1 /migrations/*.sql | sort); do
  echo "-> $f"
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f"
done
echo "Migrations complete."
