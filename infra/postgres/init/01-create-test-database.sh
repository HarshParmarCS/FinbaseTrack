#!/bin/sh
# Runs once on first start of an empty data volume (official postgres image convention).
# Creates "<POSTGRES_DB>_test" so the backend test suite never touches development data.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
    CREATE DATABASE "${POSTGRES_DB}_test" OWNER "$POSTGRES_USER";
EOSQL
