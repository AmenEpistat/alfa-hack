FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/server:/app:/app/parser/src:/app/preprocessing:/app/ranking_module/src \
    DATABASE_URL=sqlite:////app/state/backend.db \
    HF_HOME=/app/.cache/huggingface \
    HF_HUB_CACHE=/app/.cache/huggingface/hub \
    ALPHA_TESSDATA=/usr/share/tesseract-ocr/5/tessdata \
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng libgomp1 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY docker/requirements.lock /app/docker/requirements.lock
RUN python -m pip install --no-cache-dir --require-hashes -r docker/requirements.lock
COPY server /app/server
COPY parser /app/parser
COPY ranking_module /app/ranking_module
COPY preprocessing /app/preprocessing
COPY insides /app/insides
COPY backend.py pipeline_adapter.py /app/
RUN useradd --uid 10001 --create-home app \
    && mkdir -p /app/state /app/cache /app/output /app/inputs /app/.cache/huggingface /app/ranking_module/cache /app/ranking_module/runs /app/ranking_module/models \
    && chown -R app:app /app/state /app/cache /app/output /app/inputs /app/.cache /app/ranking_module/cache /app/ranking_module/runs /app/ranking_module/models
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/',timeout=3)"
CMD ["python", "-m", "uvicorn", "app.main:app", "--app-dir", "server", "--host", "0.0.0.0", "--port", "8000"]
