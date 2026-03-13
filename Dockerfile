FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --timeout 300 --retries 5 \
    torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir --timeout 300 --retries 5 fastapi
RUN pip install --no-cache-dir --timeout 300 --retries 5 "uvicorn[standard]"
RUN pip install --no-cache-dir --timeout 300 --retries 5 pydantic pydantic-settings python-dotenv
RUN pip install --no-cache-dir --timeout 300 --retries 5 asyncpg pgvector
RUN pip install --no-cache-dir --timeout 300 --retries 5 numpy
RUN pip install --no-cache-dir --timeout 300 --retries 5 scikit-learn
RUN pip install --no-cache-dir --timeout 300 --retries 5 joblib
RUN pip install --no-cache-dir --timeout 300 --retries 5 sentence-transformers
RUN pip install --no-cache-dir --timeout 300 --retries 5 lightgbm
RUN pip install --no-cache-dir --timeout 300 --retries 5 aiokafka
RUN pip install --no-cache-dir --timeout 300 --retries 5 "redis[hiredis]"
RUN pip install --no-cache-dir --timeout 300 --retries 5 py-eureka-client

COPY app/ ./app/
COPY schema.sql .

RUN mkdir -p models

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
