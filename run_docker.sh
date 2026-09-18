#!/usr/bin/env bash
# ==============================================================================
# GridWise Docker Build & Run Script
# Conforms to BUP CSE Fest 2026 Guidelines (Section 02 & 03)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

IMAGE_NAME="gridwise-api"
IMAGE_TAG="${1:-latest}"
CONTAINER_NAME="gridwise-server"
HOST_PORT="${PORT:-8000}"

echo "======================================================"
echo " Building Docker Image: ${IMAGE_NAME}:${IMAGE_TAG}     "
echo "======================================================"

# Build image without baking any secrets
docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" .

echo "======================================================"
echo " Running Container: ${CONTAINER_NAME}                  "
echo "======================================================"

# Remove existing container if present
docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true

# Prepare environment variable flags
ENV_FLAGS=()
if [ -f ".env" ]; then
    echo "Passing environment variables from .env..."
    ENV_FLAGS+=(--env-file .env)
else
    [ -n "${GEMINI_API_KEY:-}" ] && ENV_FLAGS+=(-e GEMINI_API_KEY="${GEMINI_API_KEY}")
    [ -n "${OPENAI_API_KEY:-}" ] && ENV_FLAGS+=(-e OPENAI_API_KEY="${OPENAI_API_KEY}")
    [ -n "${GROQ_API_KEY:-}" ] && ENV_FLAGS+=(-e GROQ_API_KEY="${GROQ_API_KEY}")
    [ -n "${LLM_MODEL:-}" ] && ENV_FLAGS+=(-e LLM_MODEL="${LLM_MODEL}")
    [ -n "${SUPABASE_URL:-}" ] && ENV_FLAGS+=(-e SUPABASE_URL="${SUPABASE_URL}")
    [ -n "${SUPABASE_SERVICE_KEY:-}" ] && ENV_FLAGS+=(-e SUPABASE_SERVICE_KEY="${SUPABASE_SERVICE_KEY}")
fi

# Run container as non-root user (configured in Dockerfile)
docker run --rm \
    --name "${CONTAINER_NAME}" \
    -p "${HOST_PORT}:8000" \
    "${ENV_FLAGS[@]}" \
    "${IMAGE_NAME}:${IMAGE_TAG}"
