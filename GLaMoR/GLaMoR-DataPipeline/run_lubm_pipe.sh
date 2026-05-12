#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
CONSOLIDATED_OWL_DIR="${CONSOLIDATED_OWL_DIR:-./data/lubm_c}"
MANIFEST_PATH="${MANIFEST_PATH:-./data/filtered_dataset.csv}"
UNIVERSITY_LIMIT="${UNIVERSITY_LIMIT:-100}"
QUEUE_SNAPSHOT_INTERVAL_SECONDS="${QUEUE_SNAPSHOT_INTERVAL_SECONDS:-20}"
REQUIRED_STABLE_POLLS="${REQUIRED_STABLE_POLLS:-3}"
UNIVERSITY_RESULTS="${UNIVERSITY_RESULTS:-./university_results.csv}"
default_publish_timeout_seconds=$(( UNIVERSITY_LIMIT * 45 ))
if (( default_publish_timeout_seconds < 4500 )); then
  default_publish_timeout_seconds=4500
fi
PUBLISH_TIMEOUT_SECONDS="${PUBLISH_TIMEOUT_SECONDS:-$default_publish_timeout_seconds}"
PUBLISH_IDLE_TIMEOUT_SECONDS="${PUBLISH_IDLE_TIMEOUT_SECONDS:-900}"
require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd" >&2
    exit 1
  fi
}
require_cmd docker
require_cmd python
require_cmd awk
require_cmd find
if [[ ! -d "$CONSOLIDATED_OWL_DIR" ]]; then
  echo "Consolidated ontology directory not found: $CONSOLIDATED_OWL_DIR" >&2
  exit 1
fi
mkdir -p ./data/ont_modules ./data/processed_modules ./data/prefixless_modules ./data/triples ./data/filtered_modules
mkdir -p ./data/filtered_modules/consistent/500 ./data/filtered_modules/consistent/1000 ./data/filtered_modules/consistent/4000
mkdir -p ./data/filtered_modules/inconsistent/500 ./data/filtered_modules/inconsistent/1000 ./data/filtered_modules/inconsistent/4000
mkdir -p ./data/filtered_modules/overThreshold
echo "[0/8] Cleaning previous generated artifacts"
find ./data/ont_modules -type f -delete
find ./data/processed_modules -type f -delete
find ./data/prefixless_modules -type f -delete
find ./data/triples -type f -delete
find ./data/filtered_modules -type f -delete
rm -f "$UNIVERSITY_RESULTS"
export CONSOLIDATED_OWL_DIR MANIFEST_PATH UNIVERSITY_LIMIT
python - <<'PY'
import csv
import os
from pathlib import Path
src = Path(os.environ["CONSOLIDATED_OWL_DIR"]).resolve()
out = Path(os.environ["MANIFEST_PATH"]).resolve()
limit = int(os.environ["UNIVERSITY_LIMIT"])
data_root = (Path.cwd() / "data").resolve()
if not src.exists():
    raise SystemExit(f"Missing consolidated input directory: {src}")
try:
    rel_dir = src.relative_to(data_root)
except ValueError as exc:
    raise SystemExit(f"{src} must live under {data_root}") from exc
rows = sorted(src.glob("*.owl"))[:limit]
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle)
    writer.writerow(["file_name", "consistency", "tokenized_length", "body", "inconsistency"])
    for path in rows:
        writer.writerow([f"{rel_dir.as_posix()}/{path.name}", "", "", "", ""])
print(f"Prepared {len(rows)} consolidated universities in {out}")
PY
EXPECTED_UNIVERSITIES="$(python - <<'PY'
import csv
from pathlib import Path
p = Path('./data/filtered_dataset.csv')
with p.open('r', newline='', encoding='utf-8') as handle:
    rows = list(csv.DictReader(handle))
print(len(rows))
PY
)"
echo "[1/8] Restarting base services"
docker compose down --remove-orphans
docker compose up -d rabbitmq postgres
echo "[2/8] Waiting for RabbitMQ"
for _ in $(seq 1 40); do
  if docker compose exec rabbitmq rabbitmqctl await_startup >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
echo "[3/8] Purging working queues"
for q in Ontologies Modules_Preprocess Prefix_Removal Translation filtering Modules_Modify Remove_Prefix; do
  docker compose exec rabbitmq rabbitmqctl purge_queue "$q" >/dev/null 2>&1 || true
done
echo "[4/8] Starting upstream pipeline (Department Splitter -> Preprocessing -> Prefix_Removal -> Translation)"
docker compose up -d department-splitter preprocess prefix_removal translation
docker compose up -d --force-recreate start
echo "[5/8] Waiting for queue drain and triples output"
echo "Using publish timeout=${PUBLISH_TIMEOUT_SECONDS}s idle-timeout=${PUBLISH_IDLE_TIMEOUT_SECONDS}s queue-poll=${QUEUE_SNAPSHOT_INTERVAL_SECONDS}s"
downstream_start_ts=$(date +%s)
last_progress_ts=$downstream_start_ts
stable_polls=0
triples_count=0
prev_snapshot=""
while true; do
  snapshot="$(python - <<'PY'
import base64
import json
import urllib.request
url = 'http://127.0.0.1:15672/api/queues/%2F'
req = urllib.request.Request(url)
req.add_header('Authorization', 'Basic ' + base64.b64encode(b'rabbitmq_user:rabbitmq_password').decode())
with urllib.request.urlopen(req, timeout=20) as resp:
    data = json.load(resp)
ready = unacked = consumers = 0
for queue in data:
    if queue['name'] in {'Ontologies', 'Modules_Preprocess', 'Prefix_Removal', 'Translation'}:
        ready += queue.get('messages_ready', 0) or 0
        unacked += queue.get('messages_unacknowledged', 0) or 0
        consumers += queue.get('consumers', 0) or 0
print(f'{ready} {unacked} {consumers}')
PY
)"
  ready="$(echo "$snapshot" | awk '{print $1+0}')"
  unacked="$(echo "$snapshot" | awk '{print $2+0}')"
  consumers="$(echo "$snapshot" | awk '{print $3+0}')"
  modules_count="$(find ./data/ont_modules -maxdepth 1 -type f | wc -l | tr -d ' ')"
  processed_count="$(find ./data/processed_modules -maxdepth 1 -type f | wc -l | tr -d ' ')"
  prefixless_count="$(find ./data/prefixless_modules -maxdepth 1 -type f | wc -l | tr -d ' ')"
  triples_count="$(find ./data/triples -maxdepth 1 -type f | wc -l | tr -d ' ')"
  current_snapshot="$ready|$unacked|$modules_count|$processed_count|$prefixless_count|$triples_count"
  if [[ "$current_snapshot" != "$prev_snapshot" ]]; then
    last_progress_ts=$(date +%s)
    prev_snapshot="$current_snapshot"
  fi
  if (( ready == 0 && unacked == 0 && triples_count > 0 )); then
    stable_polls=$((stable_polls + 1))
  else
    stable_polls=0
  fi
  echo "queues ready=$ready unacked=$unacked consumers=$consumers modules=$modules_count processed=$processed_count prefixless=$prefixless_count triples=$triples_count stable=${stable_polls}/${REQUIRED_STABLE_POLLS}"
  if (( stable_polls >= REQUIRED_STABLE_POLLS )); then
    break
  fi
  now_ts=$(date +%s)
  if (( now_ts - downstream_start_ts > PUBLISH_TIMEOUT_SECONDS )); then
    echo "Timed out waiting for downstream drain/triples readiness after ${PUBLISH_TIMEOUT_SECONDS}s (ready=$ready unacked=$unacked modules=$modules_count processed=$processed_count prefixless=$prefixless_count triples=$triples_count)" >&2
    exit 1
  fi
  if (( now_ts - last_progress_ts > PUBLISH_IDLE_TIMEOUT_SECONDS )); then
    echo "Timed out waiting for downstream drain/triples readiness due to ${PUBLISH_IDLE_TIMEOUT_SECONDS}s without progress (ready=$ready unacked=$unacked modules=$modules_count processed=$processed_count prefixless=$prefixless_count triples=$triples_count)" >&2
    exit 1
  fi
  sleep "$QUEUE_SNAPSHOT_INTERVAL_SECONDS"
done
if (( triples_count == 0 )); then
  echo "No triples were produced; refusing to run classifier batch." >&2
  exit 1
fi
echo "[6/8] Running classifier batch once"
docker compose stop filtering >/dev/null 2>&1 || true
docker compose run --rm --no-deps filtering
echo "[7/8] Aggregating module predictions to university results"
python aggregate_predictions.py ./data/filtered_modules/predictions.csv "$UNIVERSITY_RESULTS"
echo "[8/8] Summarizing outputs"
python - <<'PY'
import csv
import sys
from collections import Counter
from pathlib import Path
csv.field_size_limit(sys.maxsize)
dataset_path = Path('./data/filtered_modules/dataset.csv')
predictions_path = Path('./data/filtered_modules/predictions.csv')
results_path = Path('./university_results.csv')
if dataset_path.exists():
    with dataset_path.open('r', newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    print('dataset_rows:', len(rows))
    print('dataset_path:', dataset_path)
if predictions_path.exists():
    with predictions_path.open('r', newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    c = Counter((row.get('consistency') or '').strip().lower() for row in rows)
    print('prediction_rows:', len(rows))
    print('prediction_counts:', dict(c))
    print('predictions_path:', predictions_path)
if results_path.exists():
    with results_path.open('r', newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    print('university_rows:', len(rows))
    print('results_path:', results_path)
PY
echo "Expected consolidated universities: $EXPECTED_UNIVERSITIES"
echo "Done."
