# syntax=docker/dockerfile:1
# FastAPI backend. Python 3.12 matches the version the project is developed and tested on.

# ---- build stage: install dependencies into a virtual environment ----------------------------
FROM docker.io/library/python:3.12-slim AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# ---- runtime stage --------------------------------------------------------------------------
FROM docker.io/library/python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN groupadd --system app && useradd --system --gid app --home-dir /app --no-create-home app
COPY --from=build /opt/venv /opt/venv

WORKDIR /app
# Only what the application needs at runtime. No .env, tests or local caches (see .dockerignore):
# all configuration comes from environment variables set by docker-compose.yml.
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh

USER app
EXPOSE 8000

# Liveness: the health endpoint does not touch the database (decision D13).
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2).status == 200 else 1)"

ENTRYPOINT ["entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
