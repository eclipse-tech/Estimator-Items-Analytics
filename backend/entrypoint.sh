#!/bin/sh
set -e

# Set APP_ENVIRONMENT from env (single source for scripts and APIs)
# Fallback: APP_ENVIRONMENT, then ENRICH_ENVIRONMENT, then "dev"
if [ -n "$APP_ENVIRONMENT" ]; then
  export APP_ENVIRONMENT
  export ENRICH_ENVIRONMENT="$APP_ENVIRONMENT"
  echo "Using APP_ENVIRONMENT: $APP_ENVIRONMENT"
elif [ -n "$ENRICH_ENVIRONMENT" ]; then
  export APP_ENVIRONMENT="$ENRICH_ENVIRONMENT"
  echo "Using APP_ENVIRONMENT: $APP_ENVIRONMENT (from ENRICH_ENVIRONMENT)"
else
  export APP_ENVIRONMENT="dev"
  export ENRICH_ENVIRONMENT="dev"
  echo "APP_ENVIRONMENT not set, defaulting to: dev"
fi

# Project resources folder (inside container this is typically /app/resources).
# Resolve relative to this script so it works regardless of WORKDIR.
ENTRYPOINT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
RESOURCES_DIR="${ENTRYPOINT_DIR}/resources"
CLEANUP_JSON="${RESOURCES_DIR}/items_with_identifiers.json"
CLEANUP_CSV="${RESOURCES_DIR}/item_identifiers_map.csv"
CLEANUP_CITY_CSV="${RESOURCES_DIR}/city.csv"
CLEANUP_CITY_JSON="${RESOURCES_DIR}/city_canonical_mapping.json"

cleanup() {
  echo "Stopping: removing generated files..."
  rm -f "$CLEANUP_JSON" "$CLEANUP_CSV" "$CLEANUP_CITY_CSV" "$CLEANUP_CITY_JSON"
  echo "Removed items_with_identifiers.json and item_identifiers_map.csv"
  echo "Removed city.csv and city_canonical_mapping.json"
}

on_exit() {
  kill $UVICORN_PID 2>/local/null || true
  wait $UVICORN_PID 2>/local/null || true
  cleanup
  exit 0
}

# Use signal numbers for portability (dash/ash in minimal images)
# 15 = SIGTERM, 2 = SIGINT
trap on_exit 15 2

echo "Running enrich_static_items.py..."
python scripts/enrich_static_items.py || true

echo "Running enrich_items_with_identifiers.py..."
python scripts/enrich_items_with_identifiers.py || true

echo "Running fetch_cities.py..."
python scripts/fetch_cities.py || true

echo "Starting uvicorn..."
uvicorn routes.controller:app --host 0.0.0.0 --port 8090 &
UVICORN_PID=$!
wait $UVICORN_PID
cleanup
exit 0
