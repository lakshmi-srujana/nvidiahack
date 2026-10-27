FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock
COPY backend/pyproject.toml ./
COPY backend/config ./config
COPY backend/app ./app
COPY backend/bench ./bench
COPY simulator ./simulator
COPY verifier ./verifier
RUN pip install --no-cache-dir --no-deps . \
    && useradd --create-home --uid 10001 appuser
ENV PYTHONPATH=/app
ENV APP_MODE=production
EXPOSE 8000
USER appuser
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
