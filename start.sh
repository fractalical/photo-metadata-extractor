#!/usr/bin/env bash
# Photo Metadata Extractor — Linux / macOS launcher
set -e

echo ""
echo "╔══════════════════════════════════════╗"
echo "║    Photo Metadata Extractor          ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── Check prerequisites ───────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "ERROR: Docker is not installed."
    echo "Install it from: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker info &>/dev/null 2>&1; then
    echo "ERROR: Docker is not running. Please start Docker and try again."
    exit 1
fi

# ── Load .env if present ──────────────────────────────────────────────────────
if [ -f .env ]; then
    # Export only non-comment, non-empty lines
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

# ── Derive BROWSE_ROOT from PHOTOS_DIR if not set ────────────────────────────
if [ -z "${BROWSE_ROOT:-}" ]; then
    BROWSE_ROOT="$(dirname "${PHOTOS_DIR:-$HOME/Pictures}")"
fi

PORT="${PORT:-8080}"

echo "  Photos:  ${PHOTOS_DIR:-./photos}"
echo "  UI:      http://localhost:${PORT}"
echo ""
echo "Starting... (first run may take 2–5 minutes to build)"
echo "Press Ctrl+C to stop."
echo ""

export BROWSE_ROOT
docker compose up --build --remove-orphans
