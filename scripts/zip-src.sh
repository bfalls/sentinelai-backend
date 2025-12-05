#!/usr/bin/env bash
set -euo pipefail

# ------------------------------------------------------------------------------
# zip-src.sh
#
# Creates a clean source zip for deployment, excluding:
# - virtualenvs
# - git metadata
# - python caches / build products
# - logs, temp files
# - .env files + secrets
# - editor/IDE clutter
#
# Usage:
#   ./zip-src.sh
#
# Output:
#   build/sentinel-backend-src-YYYYMMDD-HHMMSS.zip
# ------------------------------------------------------------------------------

PROJECT_NAME="sentinel-backend"
OUTPUT_FILE="${PROJECT_NAME}.zip"

echo "Creating source zip: $OUTPUT_FILE"
echo

# Exclusion list — tuned for Python + FastAPI + typical dev clutter.
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

# Build the exclusion options for zip
ZIP_EXCLUDES=()
for pattern in "${EXCLUDES[@]}"; do
  ZIP_EXCLUDES+=("-x" "$pattern")
done

# Create the zip
rm -f "$OUTPUT_FILE"
zip -r "$OUTPUT_FILE" . "${ZIP_EXCLUDES[@]}"

echo
echo "Done"
echo "File created: $OUTPUT_FILE"
