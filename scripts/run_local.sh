#!/usr/bin/env bash
set -euo pipefail

IMAGE="animatic-local"
PORT=8000

echo "Building $IMAGE..."
docker build -t "$IMAGE" .

echo "Running on http://localhost:$PORT ..."
docker run --rm -p "$PORT:8000" \
  --env-file .env \
  "$IMAGE"
