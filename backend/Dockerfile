FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /srv

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
# Shared with the worker image. The backend only needs the HTTP surface and the
# schemas; the model calls happen worker-side, where the API keys live.
COPY multi_model_trust/ ./multi_model_trust/

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
