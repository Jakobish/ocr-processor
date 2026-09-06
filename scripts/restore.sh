#!/usr/bin/env bash
# Only for an isolated compose project with EMPTY volumes; never restores over an existing DB.
set -Eeuo pipefail
umask 077
cd "$(dirname "$0")/.."
: "${COMPOSE_PROJECT_NAME:?Set a unique isolated restore project name}"
: "${OCR_RESTORE_CONFIRM:?Set OCR_RESTORE_CONFIRM to isolated-empty-project}"
[[ "$OCR_RESTORE_CONFIRM" == isolated-empty-project ]] || exit 2
snapshot=${1:?Pass explicit restic snapshot ID}
if docker compose ps -aq | grep -q .; then
  echo 'Restore requires a new isolated Compose project without containers' >&2; exit 2
fi
if docker volume ls -q --filter "label=com.docker.compose.project=$COMPOSE_PROJECT_NAME" | grep -q .; then
  echo 'Restore requires a project without existing volumes' >&2; exit 2
fi
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
restic restore "$snapshot" --target "$stage"
dump=$(find "$stage" -name database.dump -type f)
archive=$(find "$stage" -name documents.tar -type f)
[[ -f "$dump" && -f "$archive" ]] || { echo 'Snapshot files missing' >&2; exit 2; }
docker compose up -d --wait postgres
docker compose exec -T postgres pg_restore -U ocr -d ocr --no-owner --exit-on-error < "$dump"
docker compose run --rm --no-deps -T --entrypoint tar api -C /app/data -xf - < "$archive"
docker compose run --rm --no-deps migrate
# Expire retained content before enabling API or browser access.
docker compose run --rm --no-deps maintenance python -m enterprise.maintenance --once
printf 'Restore and expiry completed. Inspect data and perform acceptance checks before starting services.\n'
