#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> Copying shared module into function directories..."
rm -rf functions/api/shared functions/ai/shared
cp -r functions/shared functions/api/shared
cp -r functions/shared functions/ai/shared

echo "==> Running SAM build..."
sam build --profile hackathon

echo "==> Cleaning up copied shared dirs..."
rm -rf functions/api/shared functions/ai/shared

echo "==> Build complete!"
