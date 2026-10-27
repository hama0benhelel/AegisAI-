FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --uid 10002 --create-home simulator
COPY --chown=simulator:simulator producer.py .
COPY --chown=simulator:simulator tests ./tests
USER simulator
CMD ["python", "producer.py"]
