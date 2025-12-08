#!/usr/bin/env bash
set -euo pipefail

# Build a deployable zip archive from the current Git HEAD.
# Output: writes the zip file into build/ and echoes the absolute path.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if ! command -v git >/dev/null 2>&1; then
  echo "git is required to build the deployment artifact" >&2
  exit 1
fi

BUILD_DIR="$ROOT_DIR/build"
mkdir -p "$BUILD_DIR"

TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
ARTIFACT_NAME="sentinel-backend-${TIMESTAMP}.zip"
OUTPUT_PATH="$BUILD_DIR/$ARTIFACT_NAME"

# Use git archive to avoid packaging local build artifacts or the .git directory.
git archive --format=zip --output "$OUTPUT_PATH" HEAD

echo "$OUTPUT_PATH"
