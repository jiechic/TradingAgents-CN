#!/usr/bin/env bash
set -euo pipefail
version=$(python3 tools/release_version.py)
tag=${IMAGE_TAG:-v$version}
owner=${OWNER,,}
docker network create ta-smoke
docker run -d --name mongodb --network ta-smoke \
  -e MONGO_INITDB_ROOT_USERNAME=admin -e MONGO_INITDB_ROOT_PASSWORD=ci-mongo-only mongo:8.0
docker run -d --name redis --network ta-smoke redis:7-alpine
docker run -d --name frontend --network ta-smoke -p 18080:80 \
  "ghcr.io/$owner/tradingagents-v3-frontend:$tag"
for attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:18080/ > /tmp/spa.html; then break; fi
  sleep 2
done
grep -q '<html' /tmp/spa.html
code=$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:18080/api/health)
test "$code" = 502
docker run -d --name backend --network ta-smoke -p 18000:8000 \
  -e DEBUG=false \
  -e MONGODB_HOST=mongodb -e MONGODB_PORT=27017 \
  -e MONGODB_USERNAME=admin -e MONGODB_PASSWORD=ci-mongo-only \
  -e MONGODB_DATABASE=tradingagents_ci -e MONGODB_AUTH_SOURCE=admin \
  -e 'MONGODB_CONNECTION_STRING=mongodb://admin:ci-mongo-only@mongodb:27017/tradingagents_ci?authSource=admin' \
  -e REDIS_HOST=redis -e REDIS_PORT=6379 \
  -e JWT_SECRET=ephemeral-ci-jwt-secret-unique-not-for-deployment-12345 \
  -e CSRF_SECRET=ephemeral-ci-csrf-secret-unique-not-for-deployment-67890 \
  -e ADMIN_DEFAULT_PASSWORD=Ephemeral-CI-Admin-Only-12345 \
  "ghcr.io/$owner/tradingagents-v3-backend:$tag"
ready=false
for attempt in $(seq 1 90); do
  if curl -fsS http://127.0.0.1:18080/api/health > /tmp/health.json; then ready=true; break; fi
  sleep 5
done
test "$ready" = true
python3 -c 'import json; d=json.load(open("/tmp/health.json")); assert d["success"] and d["data"]["status"]=="ok"; print("Frontend proxy recovered after backend appeared")'
curl -fsS http://127.0.0.1:18000/api/system/info > /tmp/version.json
EXPECTED_VERSION=$version python3 -c 'import json,os; d=json.load(open("/tmp/version.json")); assert d["version"] == d["full_version"] == os.environ["EXPECTED_VERSION"], d; print("Backend version and build information match")'
curl -fsS -X POST http://127.0.0.1:18080/api/auth/login \
  -H 'Content-Type: application/json' \
  --data '{"username":"admin","password":"Ephemeral-CI-Admin-Only-12345"}' > /tmp/login.json
python3 -c 'import json; d=json.load(open("/tmp/login.json")); assert d.get("success"),d.get("message"); print("Fresh administrator login passed")'
docker exec backend python -m migrations.cli status
# Changing the backend address must not require a frontend restart.
old_ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' backend)
docker network disconnect ta-smoke backend
docker run -d --name address-holder --network ta-smoke --entrypoint sleep redis:7-alpine 120
docker network connect --alias backend ta-smoke backend
new_ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' backend)
test "$old_ip" != "$new_ip"
ready=false
for attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:18080/api/health > /dev/null; then ready=true; break; fi
  sleep 3
done
test "$ready" = true
echo 'Full-stack smoke checks passed, including backend IP change'
