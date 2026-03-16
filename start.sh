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
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

# ── Auto-detect BROWSE_ROOT based on OS ──────────────────────────────────────
if [ -z "${BROWSE_ROOT:-}" ]; then
    case "$(uname -s)" in
        Darwin) BROWSE_ROOT="/Users" ;;
        *)      BROWSE_ROOT="/home"  ;;
    esac
fi
export BROWSE_ROOT

PORT="${PORT:-8080}"

echo "  UI:  http://localhost:${PORT}"
echo ""
echo "Starting... (first run may take 2–5 minutes to build)"
echo "Press Ctrl+C to stop."
echo ""

docker compose up --build --remove-orphans
