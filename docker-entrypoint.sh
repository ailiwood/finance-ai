#!/bin/bash
# QuantSage Docker Entry Point
# Usage: docker run quantsage [ui|kronos|finbert|all]

set -e

# Copy .env.example if .env doesn't exist
if [ ! -f /app/.env ]; then
    cp /app/.env.example /app/.env
    echo "[QuantSage] Created .env from .env.example. Please edit with your API keys."
fi

SERVICE="${1:-ui}"

case "$SERVICE" in
    ui)
        echo "[QuantSage] Starting Streamlit UI on port 8501..."
        exec python -m streamlit run src/ui/app.py --server.port=8501 --server.address=0.0.0.0
        ;;
    kronos)
        echo "[QuantSage] Starting Kronos K-line prediction service on port 8100..."
        exec python -m uvicorn src.plugins.kronos_service.service:app --host 0.0.0.0 --port 8100
        ;;
    finbert)
        echo "[QuantSage] Starting FinBERT sentiment service on port 8101..."
        exec python -m uvicorn src.plugins.finbert_service.service:app --host 0.0.0.0 --port 8101
        ;;
    all)
        echo "[QuantSage] Starting all services..."
        python -m uvicorn src.plugins.kronos_service.service:app --host 0.0.0.0 --port 8100 &
        python -m uvicorn src.plugins.finbert_service.service:app --host 0.0.0.0 --port 8101 &
        exec python -m streamlit run src/ui/app.py --server.port=8501 --server.address=0.0.0.0
        ;;
    *)
        echo "Usage: docker run quantsage [ui|kronos|finbert|all]"
        exit 1
        ;;
esac
