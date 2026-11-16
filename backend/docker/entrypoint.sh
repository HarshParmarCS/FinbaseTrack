#!/bin/sh
# Container entrypoint: apply database migrations (once, under an advisory lock), then start the
# API. Set RUN_MIGRATIONS=false to skip the migration step (for example for a second replica).
set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  python -m scripts.migrate
fi

exec "$@"
