#!/bin/bash
set -euo pipefail

# Only run in remote (Claude Code on the web) environments
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

# ── Ensure .env exists (copy from template if missing) ──
if [ ! -f .env ] && [ -f .env.template ]; then
  cp .env.template .env
  echo "Created .env from template — add your API keys to .env for live data"
fi

# ── Python dependencies ──
# Install core deps individually (yfinance has a known upstream build issue with multitasking)
pip install \
  "fastapi>=0.110" "uvicorn[standard]>=0.27" "sqlalchemy[asyncio]>=2.0" \
  "asyncpg>=0.29" "alembic>=1.13" "pydantic>=2.6" "pydantic-settings>=2.1" \
  "httpx>=0.27" "numpy>=1.26" "pandas>=2.2" "scipy>=1.12" \
  "scikit-learn>=1.4" "statsmodels>=0.14" "redis>=5.0" "apscheduler>=3.10" \
  "websockets>=12.0" "python-dotenv>=1.0" "aiofiles>=23.2" "aiohttp>=3.9" \
  "orjson>=3.9" "python-dateutil>=2.8" \
  aiosqlite \
  --quiet 2>&1 | tail -5

# Dev dependencies
pip install "pytest>=8.0" "pytest-asyncio>=0.23" "ruff>=0.3" --quiet 2>&1 | tail -3

# yfinance optional — may fail on some platforms
pip install "yfinance>=0.2" --quiet 2>/dev/null || echo "Note: yfinance skipped (optional)"

# ── Frontend dependencies + build ──
if [ -f frontend/package.json ]; then
  cd frontend
  npm install --prefer-offline --no-audit --no-fund 2>&1 | tail -3
  npm run build 2>&1 | tail -3
  cd "$CLAUDE_PROJECT_DIR"
fi

# ── Database migrations ──
if [ -f alembic.ini ]; then
  python -m alembic upgrade head 2>&1 | tail -3
fi

# ── Start the backend server ──
# Kill any existing uvicorn instance (avoid killing this script)
pgrep -f "uvicorn backend.main:app" | grep -v $$ | xargs -r kill 2>/dev/null || true
sleep 1

nohup python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --log-level info > /tmp/upst-server.log 2>&1 &

# Wait for server to be ready
for i in $(seq 1 20); do
  if curl -s http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    echo "UPST server running on http://localhost:8000"
    break
  fi
  sleep 1
done

# ── Export useful env vars ──
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo 'export PYTHONPATH="."' >> "$CLAUDE_ENV_FILE"
  echo 'export UPST_SERVER_URL="http://localhost:8000"' >> "$CLAUDE_ENV_FILE"
fi
