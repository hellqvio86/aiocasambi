#!/usr/bin/env bash
set -euo pipefail

# bin/renovate/run.sh - Run Renovate CLI locally via Docker container
#
# Supports:
#   - Local dry-run inspection (default, no GitHub credentials needed)
#   - Full remote runs against GitHub (with GITHUB_TOKEN or RENOVATE_TOKEN)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

if [[ -f "${REPO_ROOT}/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  . "${REPO_ROOT}/.env"
  set +a
fi

CACHE_DIR="${HOME}/.cache/renovate"
RENOVATE_IMAGE="${RENOVATE_IMAGE:-ghcr.io/renovatebot/renovate:latest}"
LOG_LEVEL="${LOG_LEVEL:-info}"
DRY_RUN="full"
PLATFORM=""
TOKEN="${RENOVATE_TOKEN:-${GITHUB_TOKEN:-}}"
REPO_NAME="hellqvio86/aiocasambi"

SUMMARY="false"

show_help() {
  cat <<'EOF'
Usage: ./bin/renovate/run.sh [OPTIONS]

Run Renovate locally inside a container against this repository.

Options:
  -s, --summary            Print a clean summary of proposed upgrade branches
  -w, --write, --apply     Live mode: create/update local git branches (equivalent to --dry-run null)
  -d, --dry-run <mode>     Dry-run mode: 'full' (default), 'lookup', or 'null' (live write)
  -l, --log-level <level>  Log level: info (default), debug, warn, error
  -t, --token <token>      GitHub Personal Access Token (or set GITHUB_TOKEN / RENOVATE_TOKEN)
  -p, --platform <name>    Platform: 'local' (default without token) or 'github'
  --cache-dir <dir>        Directory to store Renovate cache (default: ~/.cache/renovate)
  -h, --help               Show this help message and exit

Examples:
  # View clean summary list of available update branches (no tokens needed):
  ./bin/renovate/run.sh --summary

  # Create local git branches and commits for updates:
  ./bin/renovate/run.sh --write

  # Detailed debug inspection:
  ./bin/renovate/run.sh --log-level debug

  # Check with GitHub token in dry-run mode (simulates remote PR creation):
  GITHUB_TOKEN="ghp_xxx" ./bin/renovate/run.sh
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      show_help
      exit 0
      ;;
    -s|--summary)
      SUMMARY="true"
      LOG_LEVEL="debug"
      shift
      ;;
    -w|--write|--apply|--no-dry-run)
      DRY_RUN="null"
      shift
      ;;
    -d|--dry-run)
      if [[ $# -lt 2 ]]; then
        echo "Error: $1 requires a mode argument (full, lookup, null)." >&2
        exit 1
      fi
      DRY_RUN="$2"
      shift 2
      ;;
    --dry-run=*)
      DRY_RUN="${1#*=}"
      shift
      ;;
    -l|--log-level)
      if [[ $# -lt 2 ]]; then
        echo "Error: $1 requires a level argument." >&2
        exit 1
      fi
      LOG_LEVEL="$2"
      shift 2
      ;;
    --log-level=*)
      LOG_LEVEL="${1#*=}"
      shift
      ;;
    -t|--token)
      if [[ $# -lt 2 ]]; then
        echo "Error: $1 requires a token argument." >&2
        exit 1
      fi
      TOKEN="$2"
      shift 2
      ;;
    --token=*)
      TOKEN="${1#*=}"
      shift
      ;;
    -p|--platform)
      if [[ $# -lt 2 ]]; then
        echo "Error: $1 requires a platform argument (local, github)." >&2
        exit 1
      fi
      PLATFORM="$2"
      shift 2
      ;;
    --platform=*)
      PLATFORM="${1#*=}"
      shift
      ;;
    --cache-dir)
      if [[ $# -lt 2 ]]; then
        echo "Error: $1 requires a directory path." >&2
        exit 1
      fi
      CACHE_DIR="$2"
      shift 2
      ;;
    --cache-dir=*)
      CACHE_DIR="${1#*=}"
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      show_help
      exit 1
      ;;
  esac
done

# Auto-detect GitHub credentials from gh CLI if not explicitly passed
GH_SOURCE="manual"
if [[ -z "$TOKEN" ]] && command -v gh >/dev/null 2>&1; then
  TOKEN="$(gh auth token 2>/dev/null || true)"
  if [[ -n "$TOKEN" ]]; then
    GH_SOURCE="gh-cli"
  fi
fi

# If platform was not explicitly set, deduce based on token presence
if [[ -z "$PLATFORM" ]]; then
  if [[ -n "$TOKEN" ]]; then
    PLATFORM="github"
  else
    PLATFORM="local"
  fi
fi

# Detect git author
GIT_AUTHOR_NAME="$(git config user.name 2>/dev/null || true)"
GIT_AUTHOR_EMAIL="$(git config user.email 2>/dev/null || true)"
if [[ -n "$GIT_AUTHOR_NAME" && -n "$GIT_AUTHOR_EMAIL" ]]; then
  GIT_AUTHOR="${GIT_AUTHOR_NAME} <${GIT_AUTHOR_EMAIL}>"
else
  GIT_AUTHOR="Olof Hellqvist <olof.hellqvist@gmail.com>"
fi

mkdir -p "$CACHE_DIR"

echo "=== 🚀 Running Renovate Locally ==="
echo "Platform:   ${PLATFORM}"
if [[ "$PLATFORM" == "github" ]]; then
  if [[ "$GH_SOURCE" == "gh-cli" ]]; then
    echo "Auth:       GitHub CLI (auto-detected via gh)"
  else
    echo "Auth:       Custom token provided"
  fi
fi
echo "Git Author: ${GIT_AUTHOR}"
echo "Dry Run:    ${DRY_RUN}"
echo "Log Level:  ${LOG_LEVEL}"
echo "Cache Dir:  ${CACHE_DIR}"
echo "Image:      ${RENOVATE_IMAGE}"

# Prepare Docker run arguments
DOCKER_ARGS=(
  docker run --rm -i
  --user "$(id -u):$(id -g)"
  --group-add 0
  -e "HOME=/tmp"
  -e "LOG_LEVEL=${LOG_LEVEL}"
  -e "RENOVATE_DRY_RUN=${DRY_RUN}"
  -e "RENOVATE_PLATFORM=${PLATFORM}"
  -e "RENOVATE_GIT_AUTHOR=${GIT_AUTHOR}"
  -e "RENOVATE_CACHE_DIR=/tmp/renovate/cache"
  -e "RENOVATE_CONFIG_FILE=/usr/src/app/renovate.json"
  -e "RENOVATE_REQUIRE_CONFIG=ignored"
  -e "RENOVATE_ONBOARDING=false"
  -v "${CACHE_DIR}:/tmp/renovate/cache"
  -v "${REPO_ROOT}:/usr/src/app"
  -w "/usr/src/app"
)

if [[ -t 0 ]]; then
  DOCKER_ARGS+=(-t)
fi

if [[ "$PLATFORM" == "local" ]]; then
  DOCKER_ARGS+=(
    "$RENOVATE_IMAGE"
    renovate --platform=local
  )
else
  if [[ -z "$TOKEN" ]]; then
    echo "❌ Error: Platform is '${PLATFORM}' but no GitHub token was provided." >&2
    echo "Pass --token <token> or export GITHUB_TOKEN / RENOVATE_TOKEN." >&2
    exit 1
  fi
  DOCKER_ARGS+=(
    -e "RENOVATE_TOKEN=${TOKEN}"
    -e "RENOVATE_REPOSITORIES=[\"${REPO_NAME}\"]"
    "$RENOVATE_IMAGE"
    renovate
  )
fi

if [[ "$SUMMARY" == "true" ]]; then
  echo "Scanning dependencies and evaluating upgrades..."
  TMP_LOG="$(mktemp)"
  "${DOCKER_ARGS[@]}" > "$TMP_LOG" 2>&1 || true

  echo
  echo "=== 📋 Detected Renovate Upgrade Branches ==="
  BRANCHES=$(grep -E '"branchName": "renovate/' "$TMP_LOG" | sed -E 's/.*"branchName": "(.*)".*/  - \1/' | sort -u || true)
  if [[ -n "$BRANCHES" ]]; then
    echo "$BRANCHES"
    echo
    echo "Tip: Run './bin/renovate/run.sh --write' to create these branches and open PRs."
  else
    echo "  (No update branches proposed)"
  fi
  rm -f "$TMP_LOG"
else
  "${DOCKER_ARGS[@]}"
fi
