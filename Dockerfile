FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1\
    user=postgres\
    password=7474\
    database=test_brainiac\
    host=localhost\
    port=5432


WORKDIR /app

RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir asyncpg dotenv mcp uvicorn

COPY src/ /app/src/
COPY cursor_skills/ /app/cursor_skills/
COPY config.env /app/config.env

WORKDIR /app/src

CMD ["python", "mcp_server.py"]
