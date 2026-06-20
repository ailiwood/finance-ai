# QuantSage Docker Image
# Multi-service capable: UI, Kronos GPU, FinBERT GPU
#
# Build: docker build -t quantsage:latest .
# Run UI: docker run -p 8501:8501 --env-file .env quantsage:latest
# Run GPU: docker run --gpus all -p 8100:8100 --env-file .env quantsage:latest kronos

FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.title="QuantSage"
LABEL org.opencontainers.image.description="Multi-agent stock research assistant"
LABEL org.opencontainers.image.licenses="Apache-2.0"
LABEL org.opencontainers.image.source="https://github.com/ailiwood/finance-ai"

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir \
        torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# Copy application code
COPY src/ ./src/
COPY DISCLAIMER.md .
COPY .env.example .env.example

# Create necessary directories
RUN mkdir -p /app/reports /app/cache /app/data /app/logs

# Environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Expose ports
# 8501: Streamlit UI
# 8100: Kronos prediction service
# 8101: FinBERT sentiment service
EXPOSE 8501 8100 8101

# Entry point script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["ui"]
