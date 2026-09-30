#!/bin/sh
# Nightly backups (PLAN P4.7): database dump + archive of uploaded files, kept
# BACKUP_KEEP_DAYS days in the `backups` volume. Runs once at start, then daily.
set -eu
KEEP="${BACKUP_KEEP_DAYS:-14}"
mkdir -p /backups

backup() {
  stamp=$(date +%Y-%m-%d_%H%M)
  echo "[backup] $stamp: dumping database"
  pg_dump --format=custom --file="/backups/db_$stamp.dump.tmp" && mv "/backups/db_$stamp.dump.tmp" "/backups/db_$stamp.dump"
  echo "[backup] $stamp: archiving files"
  tar -czf "/backups/files_$stamp.tar.gz.tmp" -C /files media private && mv "/backups/files_$stamp.tar.gz.tmp" "/backups/files_$stamp.tar.gz"
  find /backups -name 'db_*.dump' -mtime +"$KEEP" -delete
  find /backups -name 'files_*.tar.gz' -mtime +"$KEEP" -delete
  echo "[backup] $stamp: done ($(ls /backups | wc -l) files kept)"
}

until pg_isready -q; do sleep 2; done
while true; do
  backup || echo "[backup] FAILED"
  sleep 86400
done
