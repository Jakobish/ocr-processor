#!/usr/bin/env bash
# Host script. Requires docker compose, restic, flock, exported RESTIC_* credentials.
set -Eeuo pipefail
umask 077
cd "$(dirname "$0")/.."
: "${RESTIC_REPOSITORY:?Set an off-server restic repository}"
: "${RESTIC_PASSWORD_FILE:?Set the restic password file}"
case "$RESTIC_REPOSITORY" in
  /*|./*|../*) echo 'Backup repository must be off-server' >&2; exit 2 ;;
esac
mkdir -p backup-staging/metrics
chmod 755 backup-staging/metrics
exec 9>backup-staging/backup.lock
flock -n 9 || exit 0
metrics=backup-staging/metrics/backup.prom
last_success=0
if [[ -f "$metrics" ]]; then
  last_success=$(awk '$1 == "ocr_backup_last_success_timestamp_seconds" {print $2}' "$metrics")
fi
paused=0
finish() {
  result=$?
  trap - EXIT
  if [[ "$paused" == 1 ]]; then
    docker compose start api worker maintenance web >/dev/null || result=1
  fi
  if [[ "$result" == 0 ]]; then last_success=$(date +%s); fi
  printf 'ocr_backup_success %s\nocr_backup_last_success_timestamp_seconds %s\n' "$((result == 0))" "${last_success:-0}" > "$metrics.tmp"
  chmod 644 "$metrics.tmp"
  mv "$metrics.tmp" "$metrics"
  rm -f backup-staging/database.dump backup-staging/documents.tar
  exit "$result"
}
trap finish EXIT
# Quiesce writers for a mutually consistent DB/files snapshot. Proxy returns maintenance errors.
paused=1
docker compose stop web api worker maintenance
docker compose exec -T postgres pg_dump -U ocr -d ocr -Fc > backup-staging/database.dump
docker compose run --rm --no-deps -T --entrypoint tar api -C /app/data -cf - . > backup-staging/documents.tar
restic backup --tag ocr-enterprise backup-staging/database.dump backup-staging/documents.tar
restic forget --tag ocr-enterprise --keep-within 7d --prune
restic check
