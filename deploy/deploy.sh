#!/bin/sh
# Build and (re)start Pawdex. Runs on the server in /opt/pawdex (deploy/push.ps1 calls it).
set -eu
cd "$(dirname "$0")/.."

test -f .env || { echo "Missing /opt/pawdex/.env - copy deploy/.env.example to .env and fill it in"; exit 1; }

docker compose -f docker-compose.prod.yml up -d --build --remove-orphans

# Download and load every model now, so the first player doesn't wait minutes.
docker compose -f docker-compose.prod.yml exec -T api python -m app.warmup

. ./.env
echo "Checking https://$PAWDEX_DOMAIN/health ..."
curl -fsS --retry 10 --retry-delay 5 --retry-all-errors "https://$PAWDEX_DOMAIN/health" && echo && echo "Pawdex is live."
