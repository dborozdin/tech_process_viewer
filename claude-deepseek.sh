#!/usr/bin/env bash
# Wrapper: запускает Claude Code, направляя запросы в DeepSeek (Anthropic-compat endpoint).
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEY_FILE="$DIR/deepseek_key.txt"
[[ -f "$KEY_FILE" ]] || { echo "[claude-deepseek] $KEY_FILE not found"; exit 1; }

export ANTHROPIC_BASE_URL="https://api.deepseek.com/anthropic"
export ANTHROPIC_AUTH_TOKEN="$(tr -d '[:space:]' < "$KEY_FILE")"
export ANTHROPIC_MODEL="deepseek-chat"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="deepseek-chat"
export ANTHROPIC_SMALL_FAST_MODEL="deepseek-chat"
export API_TIMEOUT_MS="600000"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1"

exec claude "$@"
