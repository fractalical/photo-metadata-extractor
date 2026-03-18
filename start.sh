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
IMAGE="ghcr.io/fractalical/photo-metadata-extractor:latest"

echo "  UI:  http://localhost:${PORT}"
echo ""
echo "Pulling image (first run downloads ~500 MB, subsequent runs are instant)..."
docker pull "$IMAGE"
echo ""
echo "Starting... Press Ctrl+C to stop."
echo ""

docker run --rm \
    --name photo-metadata-extractor-web \
    -p "${PORT}:8080" \
    -v "${BROWSE_ROOT}:/data:rw" \
    -v "pme-model-cache:/app/models" \
    -e PME_ROOT_DIR=/data \
    -e PME_EXECUTION_PROVIDER=CPUExecutionProvider \
    -e "PME_NUM_COLORS=${NUM_COLORS:-5}" \
    -e "PME_SKIP_EXISTING=${SKIP_EXISTING:-true}" \
    -e "BROWSE_ROOT=${BROWSE_ROOT}" \
    "$IMAGE"
