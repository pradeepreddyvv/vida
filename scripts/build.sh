#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

echo "=== Vida Build Script ==="

# --- Backend: copy shared into each function ---
echo "Copying shared modules..."
rm -rf "$BACKEND_DIR/functions/api/shared" "$BACKEND_DIR/functions/ai/shared"
cp -r "$BACKEND_DIR/functions/shared" "$BACKEND_DIR/functions/api/shared"
cp -r "$BACKEND_DIR/functions/shared" "$BACKEND_DIR/functions/ai/shared"

# --- SAM Build ---
echo "Running SAM build..."
cd "$BACKEND_DIR"
sam build --profile hackathon

# --- Frontend Build ---
echo "Building frontend..."
cd "$FRONTEND_DIR"
if [ ! -d "node_modules" ]; then
  npm install
fi
npm run build

echo "=== Build complete ==="
echo "Backend: $BACKEND_DIR/.aws-sam/build/"
echo "Frontend: $FRONTEND_DIR/dist/"
