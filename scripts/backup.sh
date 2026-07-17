#!/bin/sh
# Nightly pg_dump to GCS (D27): 30-day retention. Cron on the VM, not in a container.
set -eu
STAMP=$(date +%Y%m%d)
docker compose exec -T db pg_dump -U certsleuth certsleuth | gzip > "/tmp/certsleuth-$STAMP.sql.gz"
gsutil cp "/tmp/certsleuth-$STAMP.sql.gz" gs://certsleuth-backups/
rm "/tmp/certsleuth-$STAMP.sql.gz"
gsutil ls gs://certsleuth-backups/ | head -n -30 | xargs -r gsutil rm
