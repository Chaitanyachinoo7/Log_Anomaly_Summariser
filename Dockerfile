FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY alembic.ini /app/
COPY alembic /app/alembic

RUN pip install --no-cache-dir .

CMD ["sh", "-c", "alembic upgrade head && uvicorn log_anomaly_summariser.main:app --host 0.0.0.0 --port 8000"]

