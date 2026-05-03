FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Sirf core packages — ML libraries hata diye
COPY requirements.txt .
RUN pip install --no-cache-dir \
    fastapi==0.111.0 \
    uvicorn[standard]==0.30.1 \
    sqlalchemy==2.0.31 \
    asyncpg==0.29.0 \
    alembic==1.13.2 \
    psycopg2-binary==2.9.9 \
    pydantic==2.8.0 \
    pydantic-settings==2.3.4 \
    python-jose[cryptography]==3.3.0 \
    passlib[bcrypt]==1.7.4 \
    python-multipart==0.0.9 \
    aiofiles==23.2.1 \
    redis==5.0.7 \
    celery==5.4.0 \
    boto3==1.34.144 \
    structlog==24.2.0 \
    prometheus-fastapi-instrumentator==7.0.0 \
    httpx==0.27.0 \
    pdfminer.six==20231228 \
    python-docx==1.1.2 \
    langdetect==1.0.9 \
    scikit-learn==1.5.0 \
    spacy==3.7.5 \
    datasketch==1.6.5

# Chota spaCy model
RUN python -m spacy download en_core_web_sm

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]