#!/usr/bin/env bash
# Full setup script for UPST Quant Finance Hub
set -e

cd "$(dirname "$0")/.."

echo "========================================"
echo "  UPST Quant Finance Hub v3.0 — Setup"
echo "========================================"

# 1. Python environment
echo "[1/4] Setting up Python environment..."
python -m pip install --upgrade pip
pip install -e ".[dev]"

# 2. Environment file
if [ ! -f .env ]; then
    echo "[2/4] Creating .env from template (mock mode)..."
    cp .env.template .env
    sed -i 's/MOCK_MODE=false/MOCK_MODE=true/' .env
else
    echo "[2/4] .env already exists, skipping..."
fi

# 3. Frontend
echo "[3/4] Setting up frontend..."
cd frontend
if command -v npm &> /dev/null; then
    npm install
    echo "Frontend dependencies installed. Run 'cd frontend && npm run dev' to start."
else
    echo "npm not found. Install Node.js to run the frontend."
fi
cd ..

# 4. Done
echo "[4/4] Setup complete!"
echo ""
echo "To start the backend (mock mode):"
echo "  python -m uvicorn backend.main:app --reload"
echo ""
echo "To start the frontend:"
echo "  cd frontend && npm run dev"
echo ""
echo "API docs: http://localhost:8000/docs"
echo "Frontend: http://localhost:5173"
echo ""
echo "For live data, add API keys to .env and set MOCK_MODE=false"
