#!/usr/bin/env bash
set -euo pipefail

# ------------------------------------------------------------------------------
# zip-src.sh
#
# Creates a timestamped source zip for deployment, excluding:
# - virtualenvs
# - git metadata
# - python caches / build products
# - logs, temp files
# - .env files + secrets
# - editor/IDE clutter
#
# Output:
#   build/sentinel-backend-src-YYYYMMDD-HHMMSS.zip
# ------------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$ROOT_DIR"

PROJECT_NAME="sentinel-backend"
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
OUTPUT_FILE="${PROJECT_NAME}-src-${TIMESTAMP}.zip"
BUILD_DIR="$ROOT_DIR/build"
OUTPUT_PATH="$BUILD_DIR/$OUTPUT_FILE"

mkdir -p "$BUILD_DIR"

echo "Creating source zip: $OUTPUT_FILE"
echo

EXCLUDES=(
  # Python
  "*/__pycache__/*"
  "*/__pycache__/"
  "__pycache__/*"
  "__pycache__/"
  "*.pyc"
  "*.pyo"
  "*.pyd"
  "*.so"
  "*.dylib"
  "*.zip"
  ".pytest_cache/*"
  ".mypy_cache/*"
  ".dmypy.json"

  # Virtual environments
  "venv/*"
  ".venv/*"
  "env/*"
  "ENV/*"

  # Build / dist artifacts
  "dist/*"
  "build/*"
  "*.egg-info/*"
  "*.egg"

  # Logs & temp
  "logs/*"
  "*.log"
  "*.tmp"
  "*.bak"
  "*.db"

  # Secrets
  ".env"
  ".env.*"
  "!env.example"

  # Git + GitHub metadata
  ".git/*"
  ".gitignore"
  ".gitattributes"
  ".github/*"

  # Editors / IDEs
  ".vscode/*"
  ".idea/*"

  # macOS junk
  ".DS_Store"

  # Docker + deployment local overrides
  "docker-compose.override.yml"
  "deploy/tmp/*"
)

ZIP_EXCLUDES=()
for pattern in "${EXCLUDES[@]}"; do
  ZIP_EXCLUDES+=("-x" "$pattern")
done

zip -r "$OUTPUT_PATH" . "${ZIP_EXCLUDES[@]}"

echo
echo "Done"
echo "$OUTPUT_PATH"
