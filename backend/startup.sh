#!/bin/bash
# =============================================================================
# Azure App Service startup script (optional reference).
#
# IMPORTANT (App Service + Oryx): when SCM_DO_BUILD_DURING_DEPLOYMENT=true, Oryx
# compresses the app to output.tar.gz and extracts it at runtime to a /tmp dir,
# then cd's into that dir and activates the virtualenv before running the
# startup command. So:
#   - Do NOT reference this file by absolute /home/site/wwwroot path (it lives
#     in the /tmp extract dir, not wwwroot).
#   - Do NOT `cd /home/site/wwwroot` here.
#
# RECOMMENDED Startup Command (set inline in App Service > Configuration — robust,
# does not depend on this file's location):
#   alembic upgrade head && gunicorn app.main:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --workers 2 --timeout 120 --access-logfile '-' --error-logfile '-'
#
# If you point the Startup Command at this script instead, use a RELATIVE path
# (`bash startup.sh`) so it resolves inside the extracted app dir.
#
# Required env vars (App Service > Application Settings): DATABASE_URL (asyncpg),
# REDIS_URL, JWT_SECRET_KEY, CORS_ORIGINS, WORKERS_IN_PROCESS=true.
# =============================================================================

set -e

echo "[startup] Running Alembic migrations..."
alembic upgrade head
echo "[startup] Migrations complete."

echo "[startup] Starting gunicorn..."
exec gunicorn app.main:app \
    -k uvicorn.workers.UvicornWorker \
    -b "0.0.0.0:${PORT:-8000}" \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
