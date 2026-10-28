FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY agents/gas/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 agentuser

COPY --chown=agentuser:agentuser agents/gas/app ./app
COPY --chown=agentuser:agentuser backend/app/consumption_rules.py ./app/consumption_rules.py

USER agentuser

EXPOSE 8443

CMD ["python", "-m", "app.server"]
