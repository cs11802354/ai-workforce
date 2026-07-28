FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /srv

COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY worker/ .
COPY multi_model_trust/ ./multi_model_trust/

CMD ["python", "worker.py"]
