#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
IMAGE_NAME="sapporo-gomi-deploy"
STAGE="${1:-dev}"

echo "==> クリーンアップ中..."
find "$SCRIPT_DIR" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find "$SCRIPT_DIR" -name "*.pyc" -o -name "*.pyo" | xargs rm -f 2>/dev/null || true

echo "==> Dockerイメージをビルド中..."
docker build \
  --platform linux/amd64 \
  -f "$SCRIPT_DIR/Dockerfile.deploy" \
  -t "$IMAGE_NAME" \
  "$SCRIPT_DIR"

echo "==> chalice deploy (stage: $STAGE) を実行中..."
docker run --rm \
  --platform linux/amd64 \
  -v "$SCRIPT_DIR":/app \
  -v "$HOME/.aws":/root/.aws:ro \
  -w /app \
  "$IMAGE_NAME" \
  chalice deploy --stage "$STAGE"

echo "==> デプロイ完了"
