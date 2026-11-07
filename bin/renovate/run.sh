#!/usr/bin/env bash
# Run Renovate CLI locally in dry-run mode against this repository using Docker / Podman.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

DEFAULT_REPO_NAME="$(git -C "${REPO_ROOT}" config --get remote.origin.url 2>/dev/null | sed -E 's/.*[:\/]([^\/]+\/[^\/\.]+)(\.git)?$/\1/' || :)"
REPO_NAME="${REPO_NAME:-${DEFAULT_REPO_NAME:-hellqvio86/aiocasambi}}"
PLATFORM="${PLATFORM:-github}"
DRY_RUN="${DRY_RUN:-full}"
LOG_LEVEL="${LOG_LEVEL:-debug}"
RENOVATE_IMAGE="${RENOVATE_IMAGE:-ghcr.io/renovatebot/renovate:latest}"
CACHE_DIR="${XDG_CACHE_HOME:-${HOME}/.cache}/renovate"

mkdir -p "${CACHE_DIR}"

CONTAINER_ENGINE=""
if command -v docker >/dev/null 2>&1; then
  CONTAINER_ENGINE="docker"
elif command -v podman >/dev/null 2>&1; then
  CONTAINER_ENGINE="podman"
else
  echo "Error: Neither docker nor podman was found on PATH." >&2
  exit 1
fi

GITHUB_TOKEN="${GITHUB_TOKEN:-${RENOVATE_TOKEN:-}}"
TOKEN_SOURCE="none"
if [ -n "${GITHUB_TOKEN}" ]; then
  TOKEN_SOURCE="environment variable"
elif command -v gh >/dev/null 2>&1 && gh auth token >/dev/null 2>&1; then
  GITHUB_TOKEN="$(gh auth token 2>/dev/null || :)"
  if [ -n "${GITHUB_TOKEN}" ]; then
    TOKEN_SOURCE="GitHub CLI (auto-detected via gh)"
  fi
fi

if [ -z "${GITHUB_TOKEN}" ]; then
  echo "Warning: No GITHUB_TOKEN or RENOVATE_TOKEN provided, and 'gh auth token' is unavailable." >&2
  echo "GitHub rate limits for unauthenticated requests may cause Renovate to fail." >&2
fi

SUMMARY_ONLY=0
POSITIONAL_ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --summary)
      SUMMARY_ONLY=1
      shift
      ;;
    -h|--help)
      cat <<EOF
Usage: $(basename "$0") [options] [-- <renovate-args>]

Run Renovate locally against this repository in dry-run mode.

Options:
  --summary          Run Renovate and print only detected branches / PR updates.
  -h, --help         Show this help message.

Environment variables:
  GITHUB_TOKEN       GitHub Personal Access Token (defaults to 'gh auth token').
  REPO_NAME          Repository name (defaults to '${REPO_NAME}').
  PLATFORM           Renovate platform (defaults to 'github').
  DRY_RUN            Renovate dryRun mode: full, lookup, or extract (defaults to 'full').
  LOG_LEVEL          Renovate log level: debug, info, warn, error (defaults to 'debug').
  RENOVATE_IMAGE     Renovate container image (defaults to 'ghcr.io/renovatebot/renovate:latest').
EOF
      exit 0
      ;;
    --)
      shift
      POSITIONAL_ARGS+=("$@")
      break
      ;;
    *)
      POSITIONAL_ARGS+=("$1")
      shift
      ;;
  esac
done

USER_ARGS=()
if [ ${#POSITIONAL_ARGS[@]} -gt 0 ]; then
  USER_ARGS=("${POSITIONAL_ARGS[@]}")
fi

GIT_AUTHOR_NAME="$(git -C "${REPO_ROOT}" config user.name 2>/dev/null || echo "Olof Hellqvist")"
GIT_AUTHOR_EMAIL="$(git -C "${REPO_ROOT}" config user.email 2>/dev/null || echo "olof.hellqvist@gmail.com")"
GIT_AUTHOR="${GIT_AUTHOR_NAME} <${GIT_AUTHOR_EMAIL}>"

echo "=== 🚀 Running Renovate Locally ==="
echo "Repository: ${REPO_NAME}"
echo "Platform:   ${PLATFORM}"
echo "Auth:       ${TOKEN_SOURCE}"
echo "Git Author: ${GIT_AUTHOR}"
echo "Dry Run:    ${DRY_RUN}"
echo "Log Level:  ${LOG_LEVEL}"
echo "Cache Dir:  ${CACHE_DIR}"
echo "Image:      ${RENOVATE_IMAGE}"

ENV_FILE="$(mktemp)"
trap 'rm -f "${ENV_FILE}"' EXIT

{
  echo "RENOVATE_PLATFORM=${PLATFORM}"
  echo "RENOVATE_DRY_RUN=${DRY_RUN}"
  echo "RENOVATE_LOG_LEVEL=${LOG_LEVEL}"
  echo "RENOVATE_GIT_AUTHOR=${GIT_AUTHOR}"
  echo "RENOVATE_REQUIRE_CONFIG=ignored"
  if [ -n "${GITHUB_TOKEN}" ]; then
    echo "RENOVATE_TOKEN=${GITHUB_TOKEN}"
    echo "GITHUB_COM_TOKEN=${GITHUB_TOKEN}"
  fi
} > "${ENV_FILE}"

DOCKER_CMD=(
  "${CONTAINER_ENGINE}" run --rm -i
  --user "$(id -u):$(id -g)"
  --env-file "${ENV_FILE}"
  -v "${REPO_ROOT}:/usr/src/app:ro"
  -v "${CACHE_DIR}:/tmp/renovate:rw"
  -e RENOVATE_CACHE_DIR=/tmp/renovate
  -w /usr/src/app
  "${RENOVATE_IMAGE}"
  renovate
  --local-config "/usr/src/app/renovate.json"
)

if [ ${#USER_ARGS[@]} -gt 0 ]; then
  DOCKER_CMD+=("${USER_ARGS[@]}")
fi

DOCKER_CMD+=("${REPO_NAME}")

if [ "${SUMMARY_ONLY}" -eq 1 ]; then
  echo "Scanning dependencies and evaluating upgrades..."
  OUTPUT="$("${DOCKER_CMD[@]}" 2>&1 || :)"
  echo ""
  echo "=== 📋 Detected Renovate Upgrade Branches ==="
  BRANCHES="$(echo "${OUTPUT}" | grep -o 'Branch: [^ ]*' | sed 's/Branch: //' | sort -u || :)"
  if [ -n "${BRANCHES}" ]; then
    while IFS= read -r branch; do
      [ -n "${branch}" ] && echo "  - ${branch}"
    done <<< "${BRANCHES}"
  else
    echo "  (No update branches proposed)"
  fi
else
  "${DOCKER_CMD[@]}"
fi
