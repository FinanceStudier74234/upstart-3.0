#!/usr/bin/env bash
# Run the UPST Quant Finance Hub backend
set -e

cd "$(dirname "$0")/.."

# Default to mock mode if no .env
if [ ! -f .env ]; then
    echo "No .env found. Copying template and enabling MOCK_MODE..."
    cp .env.template .env
    sed -i 's/MOCK_MODE=false/MOCK_MODE=true/' .env
fi

echo "Starting UPST Quant Finance Hub..."
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
