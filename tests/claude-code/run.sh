#!/bin/bash
# Convenience wrapper for running Claude Code against the local plugins checkout.
# Run from anywhere; script resolves paths relative to the repo root.
#
# Usage:
#   ./tests/claude-code/run.sh [check|validate|marketplace|all|botcha-ai|director|artist]
#
#   check        - Verify prerequisites (claude CLI, API keys, Python deps)
#   validate     - Validate marketplace.json and all plugin manifests
#   marketplace  - Register the local marketplace then launch Claude Code
#   botcha-ai    - Load agentlink-botcha-ai only via --plugin-dir
#   director     - Load agentlink-botcha-ai + agentlink-director via --plugin-dir
#   artist       - Load agentlink-botcha-ai + agentlink-artist via --plugin-dir (requires FAL_KEY)
#   all          - Load all three plugins via --plugin-dir (default; FAL_KEY optional, warns if unset)
#
# Environment variables:
#   FAL_KEY              - FAL.ai API key (required for artist plugin)
#   CLAUDE_TEST_WORKDIR  - Working directory for session artifacts (default: ~/.claude-agentlink-test)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PLUGINS_DIR="$REPO_ROOT/plugins"
WORK_DIR="${CLAUDE_TEST_WORKDIR:-$HOME/.claude-agentlink-test}"

CMD="${1:-all}"

# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

check_claude() {
  if ! command -v claude &>/dev/null; then
    echo "ERROR: claude CLI not found." >&2
    echo "       Install from https://claude.ai/code" >&2
    exit 1
  fi
}

check_python_deps() {
  local missing=()
  python3 -c "import yaml" 2>/dev/null       || missing+=(pyyaml)
  python3 -c "import cryptography" 2>/dev/null || missing+=(cryptography)
  if [[ ${#missing[@]} -gt 0 ]]; then
    echo "WARN: missing Python packages: ${missing[*]}" >&2
    echo "      botcha-ai scripts will fail until installed:" >&2
    echo "      pip install ${missing[*]}" >&2
  fi
}

check_fal_key() {
  if [[ -z "${FAL_KEY:-}" ]]; then
    echo "ERROR: FAL_KEY is not set." >&2
    echo "       Get a key at fal.ai/dashboard/keys, then:" >&2
    echo "       export FAL_KEY=your_key_here" >&2
    exit 1
  fi
}

run_check() {
  echo "=== Claude Code plugin prerequisite check ==="
  echo ""

  # claude CLI
  if command -v claude &>/dev/null; then
    echo "  claude CLI   : $(command -v claude)"
  else
    echo "  claude CLI   : NOT FOUND (install from https://claude.ai/code)"
  fi

  # Python
  echo "  python3      : $(command -v python3 2>/dev/null || echo 'NOT FOUND')"

  local pyver
  pyver=$(python3 -c "import yaml; print(yaml.__version__)" 2>/dev/null || echo "MISSING")
  echo "  pyyaml       : $pyver"

  pyver=$(python3 -c "import cryptography; print(cryptography.__version__)" 2>/dev/null || echo "MISSING")
  echo "  cryptography : $pyver"

  # FAL key
  if [[ -n "${FAL_KEY:-}" ]]; then
    echo "  FAL_KEY      : set"
  else
    echo "  FAL_KEY      : NOT SET (required for artist plugin)"
  fi

  # Plugin dirs
  echo ""
  echo "  Plugin directories:"
  for name in agentlink-botcha-ai agentlink-director agentlink-artist; do
    if [[ -d "$PLUGINS_DIR/$name" ]]; then
      echo "    $name : found"
    else
      echo "    $name : MISSING ($PLUGINS_DIR/$name)"
    fi
  done

  echo ""
  echo "  Work dir     : $WORK_DIR"
}

# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------

launch() {
  local plugin_args=()
  for name in "$@"; do
    plugin_args+=(--plugin-dir "$PLUGINS_DIR/$name")
  done

  mkdir -p "$WORK_DIR"

  echo "Work dir : $WORK_DIR"
  echo "Plugins  : $*"
  echo ""

  cd "$WORK_DIR"
  exec claude "${plugin_args[@]}"
}

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

case "$CMD" in
  check)
    run_check
    ;;

  validate)
    check_claude
    echo "Validating marketplace..."
    claude plugin validate "$REPO_ROOT"
    echo ""
    echo "Validating individual plugins..."
    for name in agentlink-botcha-ai agentlink-director agentlink-artist; do
      echo "  $name:"
      claude plugin validate "$PLUGINS_DIR/$name"
    done
    ;;

  marketplace)
    check_claude
    check_python_deps
    if [[ -z "${FAL_KEY:-}" ]]; then
      echo "WARN: FAL_KEY not set — agentlink-artist is loaded but image generation will fail." >&2
      echo ""
    fi
    echo "Registering local marketplace from $REPO_ROOT ..."
    claude plugin marketplace add "$REPO_ROOT"
    echo ""
    echo "Marketplace registered. Launch Claude Code and install plugins with:"
    echo "  /plugin install agentlink-botcha-ai@agentlink-skills"
    echo "  /plugin install agentlink-director@agentlink-skills"
    echo "  /plugin install agentlink-artist@agentlink-skills"
    echo ""
    mkdir -p "$WORK_DIR"
    cd "$WORK_DIR"
    exec claude
    ;;

  botcha-ai)
    check_claude
    check_python_deps
    launch agentlink-botcha-ai
    ;;

  director)
    # director skills call botcha-ai skills for auth, so load both
    check_claude
    check_python_deps
    launch agentlink-botcha-ai agentlink-director
    ;;

  artist)
    # artist needs botcha-ai for token/registration
    check_claude
    check_python_deps
    check_fal_key
    launch agentlink-botcha-ai agentlink-artist
    ;;

  all)
    check_claude
    check_python_deps
    if [[ -z "${FAL_KEY:-}" ]]; then
      echo "WARN: FAL_KEY not set — agentlink-artist is loaded but image generation will fail." >&2
      echo "      Set FAL_KEY or run './run.sh director' to suppress this warning." >&2
      echo ""
    fi
    launch agentlink-botcha-ai agentlink-director agentlink-artist
    ;;

  *)
    echo "Unknown command: $CMD" >&2
    echo "Usage: $0 [check|validate|marketplace|all|botcha-ai|director|artist]" >&2
    exit 1
    ;;
esac
