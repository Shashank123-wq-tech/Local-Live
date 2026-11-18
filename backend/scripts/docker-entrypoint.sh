#!/bin/bash
#!/bin/bash
set -Eeuo pipefail

trap 'code=$?; echo "LocaleLive: startup failed at line ${LINENO}, exit=${code}" >&2; exit "$code"' ERR

echo "LocaleLive: entrypoint started"

/opt/venv/bin/python --version

echo "LocaleLive: running database migrations"
cd /app
/opt/venv/bin/alembic upgrade head

echo "LocaleLive: starting API on port ${PORT:-10000}"
cd /app/src

exec /opt/venv/bin/python -m uvicorn main:app \
    --host 0.0.0.0 \
    --port "${PORT:-10000}" \
    --workers 1