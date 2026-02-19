#!/bin/bash
# SNAG Bench Runner
# Detects sibling repos, borrows their credentials, starts Flash if needed, runs eval.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FLASH_DIR="$SCRIPT_DIR/../timepoint-flash"
DAEDALUS_DIR="$SCRIPT_DIR/../timepoint-pro"
FLASH_PORT=8000
FLASH_PID=""

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cleanup() {
    if [ -n "$FLASH_PID" ]; then
        echo ""
        echo -e "${YELLOW}Stopping Flash server (pid $FLASH_PID)...${NC}"
        kill "$FLASH_PID" 2>/dev/null || true
        wait "$FLASH_PID" 2>/dev/null || true
        echo -e "${GREEN}Flash server stopped.${NC}"
    fi
}
trap cleanup EXIT

usage() {
    echo -e "${CYAN}SNAG Bench Runner${NC}"
    echo ""
    echo "Usage: ./run.sh [command] [options]"
    echo ""
    echo "Commands:"
    echo "  evaluate       Run full-stack evaluation (default)"
    echo "  leaderboard    Generate leaderboard from all results"
    echo "  check          Check environment only, don't run"
    echo "  help           Show this help"
    echo ""
    echo "Options (passed through to snag-bench evaluate):"
    echo "  --model MODEL        Model name (default: gemini-2.0-flash)"
    echo "  --preset PRESET      Flash preset (default: balanced)"
    echo "  --text-model MODEL   Override Flash LLM"
    echo "  --pro-model MODEL    Override Pro LLM"
    echo "  --full-stack         Run all axes"
    echo "  --dry-run            Print plan without executing"
    echo ""
    echo "Examples:"
    echo "  ./run.sh                                          # check + evaluate"
    echo "  ./run.sh evaluate --model gemini-2.0-flash --full-stack"
    echo "  ./run.sh evaluate --model deepseek-chat --full-stack --pro-model deepseek/deepseek-chat"
    echo "  ./run.sh leaderboard --output results/LEADERBOARD.md"
    echo "  ./run.sh check                                    # env check only"
    exit 0
}

# ── Environment detection ──────────────────────────────────────────────

check_env() {
    echo -e "${CYAN}SNAG Bench — environment check${NC}"
    echo ""

    # 1. Venv
    if [ -d "$SCRIPT_DIR/.venv" ]; then
        echo -e "  venv           ${GREEN}found${NC}  $SCRIPT_DIR/.venv"
    else
        echo -e "  venv           ${RED}missing${NC}  run: python3.11 -m venv .venv && source .venv/bin/activate && pip install -e ."
        return 1
    fi

    # 2. Flash repo
    if [ -d "$FLASH_DIR" ]; then
        echo -e "  timepoint-flash ${GREEN}found${NC}  $FLASH_DIR"
    else
        echo -e "  timepoint-flash ${RED}missing${NC}  expected at $FLASH_DIR"
    fi

    # 3. Flash .env
    if [ -f "$FLASH_DIR/.env" ]; then
        echo -e "  flash .env     ${GREEN}found${NC}  $FLASH_DIR/.env"

        # Check for API keys
        if grep -q 'GOOGLE_API_KEY=.\+' "$FLASH_DIR/.env" 2>/dev/null; then
            echo -e "  GOOGLE_API_KEY ${GREEN}set${NC}"
        else
            echo -e "  GOOGLE_API_KEY ${YELLOW}empty${NC}  (Flash needs at least one LLM provider)"
        fi

        if grep -q 'OPENROUTER_API_KEY=.\+' "$FLASH_DIR/.env" 2>/dev/null; then
            echo -e "  OPENROUTER_API_KEY ${GREEN}set${NC}"
        else
            echo -e "  OPENROUTER_API_KEY ${YELLOW}empty${NC}"
        fi
    else
        echo -e "  flash .env     ${RED}missing${NC}  $FLASH_DIR/.env"
    fi

    # 4. Daedalus repo
    if [ -d "$DAEDALUS_DIR" ]; then
        echo -e "  timepoint-pro ${GREEN}found${NC}  $DAEDALUS_DIR"
    else
        echo -e "  timepoint-pro ${YELLOW}missing${NC}  (Axis 2 will be skipped)"
    fi

    # 5. Daedalus .env
    if [ -f "$DAEDALUS_DIR/.env" ]; then
        echo -e "  daedalus .env  ${GREEN}found${NC}  $DAEDALUS_DIR/.env"
    else
        echo -e "  daedalus .env  ${YELLOW}missing${NC}"
    fi

    # 6. Flash server already running?
    if curl -s "http://localhost:$FLASH_PORT/health" >/dev/null 2>&1; then
        echo -e "  flash server   ${GREEN}running${NC}  http://localhost:$FLASH_PORT"
    else
        echo -e "  flash server   ${YELLOW}not running${NC}  (will start automatically)"
    fi

    echo ""
}

# ── Load creds from Flash .env ─────────────────────────────────────────

load_flash_env() {
    if [ -f "$FLASH_DIR/.env" ]; then
        echo -e "${CYAN}Loading credentials from $FLASH_DIR/.env${NC}"
        # Export non-comment, non-empty lines
        set -a
        while IFS='=' read -r key value; do
            # Skip comments and blank lines
            [[ "$key" =~ ^#.*$ ]] && continue
            [[ -z "$key" ]] && continue
            # Strip surrounding quotes from value
            value="${value%\"}"
            value="${value#\"}"
            value="${value%\'}"
            value="${value#\'}"
            # Only export if not already set in current env
            if [ -z "${!key}" ] && [ -n "$value" ]; then
                export "$key=$value"
            fi
        done < "$FLASH_DIR/.env"
        set +a
    fi

    # Also load Daedalus .env if it exists (for OPENROUTER_API_KEY etc.)
    if [ -f "$DAEDALUS_DIR/.env" ]; then
        echo -e "${CYAN}Loading credentials from $DAEDALUS_DIR/.env${NC}"
        set -a
        while IFS='=' read -r key value; do
            [[ "$key" =~ ^#.*$ ]] && continue
            [[ -z "$key" ]] && continue
            value="${value%\"}"
            value="${value#\"}"
            value="${value%\'}"
            value="${value#\'}"
            if [ -z "${!key}" ] && [ -n "$value" ]; then
                export "$key=$value"
            fi
        done < "$DAEDALUS_DIR/.env"
        set +a
    fi
}

# ── Start Flash if not running ─────────────────────────────────────────

ensure_flash() {
    if curl -s "http://localhost:$FLASH_PORT/health" >/dev/null 2>&1; then
        echo -e "${GREEN}Flash server already running on port $FLASH_PORT${NC}"
        return 0
    fi

    if [ ! -d "$FLASH_DIR" ]; then
        echo -e "${YELLOW}Flash repo not found at $FLASH_DIR — Axis 1 will use fallback scores${NC}"
        return 1
    fi

    echo -e "${CYAN}Starting Flash server on port $FLASH_PORT...${NC}"

    # Start Flash in the background
    (
        cd "$FLASH_DIR"
        # Use Flash's own venv if it exists, otherwise try system python
        if [ -d ".venv" ]; then
            source .venv/bin/activate
        fi
        python3 -m uvicorn app.main:app --host 127.0.0.1 --port "$FLASH_PORT" --log-level warning 2>&1 | while read -r line; do
            echo -e "  ${CYAN}[flash]${NC} $line"
        done
    ) &
    FLASH_PID=$!

    # Wait for Flash to become healthy
    echo -n "  Waiting for Flash health check"
    for i in $(seq 1 30); do
        if curl -s "http://localhost:$FLASH_PORT/health" >/dev/null 2>&1; then
            echo ""
            echo -e "  ${GREEN}Flash server ready (pid $FLASH_PID)${NC}"
            return 0
        fi
        # Check if process died
        if ! kill -0 "$FLASH_PID" 2>/dev/null; then
            echo ""
            echo -e "  ${RED}Flash server failed to start${NC}"
            FLASH_PID=""
            return 1
        fi
        echo -n "."
        sleep 2
    done

    echo ""
    echo -e "  ${RED}Flash server timed out after 60s${NC}"
    kill "$FLASH_PID" 2>/dev/null || true
    FLASH_PID=""
    return 1
}

# ── Activate venv ──────────────────────────────────────────────────────

activate_venv() {
    if [ -f "$SCRIPT_DIR/.venv/bin/activate" ]; then
        source "$SCRIPT_DIR/.venv/bin/activate"
    else
        echo -e "${RED}No .venv found. Run:${NC}"
        echo "  python3.11 -m venv .venv"
        echo "  source .venv/bin/activate"
        echo "  pip install -e ."
        exit 1
    fi
}

# ── Main ───────────────────────────────────────────────────────────────

COMMAND="${1:-evaluate}"

case "$COMMAND" in
    help|--help|-h)
        usage
        ;;
    check)
        check_env
        exit 0
        ;;
    evaluate)
        shift 2>/dev/null || true
        check_env
        activate_venv
        load_flash_env
        ensure_flash
        echo ""
        echo -e "${GREEN}Running SNAG Bench...${NC}"
        echo ""

        # Default to --full-stack if no args given
        if [ $# -eq 0 ]; then
            snag-bench evaluate --model gemini-2.0-flash --full-stack
        else
            snag-bench evaluate "$@"
        fi
        ;;
    run)
        shift 2>/dev/null || true
        check_env
        activate_venv
        load_flash_env
        ensure_flash
        echo ""
        echo -e "${GREEN}Running SNAG Bench v1.0...${NC}"
        echo ""
        snag-bench run "$@"
        ;;
    leaderboard)
        shift 2>/dev/null || true
        activate_venv
        snag-bench leaderboard "$@"
        ;;
    *)
        # Treat unknown command as args to evaluate
        check_env
        activate_venv
        load_flash_env
        ensure_flash
        echo ""
        echo -e "${GREEN}Running SNAG Bench...${NC}"
        echo ""
        snag-bench evaluate "$@"
        ;;
esac
