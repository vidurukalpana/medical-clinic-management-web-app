#!/bin/sh
# Records the CareFlow demo video. Needs `docker compose up` running, Ollama on this Mac and Google Chrome.
# The database is backed up first and restored afterwards, so the demo leaves no trace.
set -e
cd "$(dirname "$0")"
ROOT=..
OUT="${1:-$HOME/Desktop/CareFlow-demo.mp4}"

docker exec careflow-db-1 sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > before-demo.dump
restore() {
  docker exec -i careflow-db-1 sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --single-transaction' < before-demo.dump
  docker rm -f careflow-demo-api >/dev/null 2>&1 || true
}
trap restore EXIT

# A copy of the API whose clock reads Monday 08:15, so weekday sessions and the live queue are open.
docker rm -f careflow-demo-api >/dev/null 2>&1 || true
docker run -d --name careflow-demo-api --network careflow_default --env-file "$ROOT/.env.docker" -e CLINIC_RATE_LIMIT_ENABLED=false \
  --add-host host.docker.internal:host-gateway -p 127.0.0.1:8001:8000 \
  -e DEMO_NOW="2026-10-26T02:45:00+00:00" -v "$PWD/run_shifted.py:/app/run_shifted.py:ro" \
  careflow-api:latest sh -c "pip install --user --quiet time-machine && python run_shifted.py" >/dev/null
until curl -sf localhost:8001/api/health >/dev/null; do sleep 1; done

# Book today's demo patients (the seeder skips sessions already past when it ran), then keep that as each take's start.
python3 seed_today.py "$ROOT/.env.docker"
docker exec careflow-db-1 sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > start-of-take.dump

# The small chat model sometimes gets a detail wrong; record.js checks each answer and exits with 2 if one is off.
for attempt in 1 2 3 4 5 6 7 8; do
  docker exec -i careflow-db-1 sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --single-transaction' < start-of-take.dump
  code=0; node record.js "$ROOT/.env.docker" take || code=$?
  [ $code -eq 0 ] && break
  [ $code -ne 2 ] && exit $code
  echo "A chat answer was wrong, recording again ($attempt)"
done
[ $code -eq 0 ] || exit 2
# Soundtrack: "Inspiring Advertising - Upbeat Summer Corporate" by Rafael Krux (filmmusic.io), CC BY 4.0.
MUSIC=music/upbeat-summer-corporate.mp3
if [ ! -f "$MUSIC" ]; then
  mkdir -p music
  curl -sfL -A "CareFlowDemo/1.0" -o "$MUSIC" \
    "https://upload.wikimedia.org/wikipedia/commons/3/38/Rafael_Krux_-_Inspiring_Advertising_-_Upbeat_Summer_Corporate_%28cc-by%29_%28filmmusic%29.mp3"
fi
node render.js take "$OUT" 1.0 "$MUSIC"
echo "Video saved to $OUT"
