@echo off
REM Wrapper: запускает Claude Code, направляя запросы в DeepSeek (Anthropic-compat endpoint).
setlocal
if not exist "%~dp0deepseek_key.txt" (
  echo [claude-deepseek] deepseek_key.txt not found in %~dp0
  exit /b 1
)
set /p DEEPSEEK_KEY=<"%~dp0deepseek_key.txt"

set "ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic"
set "ANTHROPIC_AUTH_TOKEN=%DEEPSEEK_KEY%"
set "ANTHROPIC_MODEL=deepseek-chat"
set "ANTHROPIC_DEFAULT_HAIKU_MODEL=deepseek-chat"
set "ANTHROPIC_SMALL_FAST_MODEL=deepseek-chat"
set "API_TIMEOUT_MS=600000"
set "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1"

claude %*
