FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       curl \
       libpq-dev \
       ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Keep the container's Python environment outside the copied project.
RUN python -m venv /opt/venv

COPY requirements_pip.txt ./

RUN python -m pip install --no-cache-dir --upgrade pip wheel \
    && python -m pip install --no-cache-dir -r requirements_pip.txt \
    && python -m pip check

COPY . .

RUN sed -i 's/\r$//' /app/scripts/docker-entrypoint.sh \
    && chmod 755 /app/scripts/docker-entrypoint.sh \
    && /bin/bash -n /app/scripts/docker-entrypoint.sh \
    && test -f /app/src/main.py \
    && test -f /app/alembic.ini

WORKDIR /app/src

EXPOSE 10000

ENTRYPOINT ["/bin/bash", "/app/scripts/docker-entrypoint.sh"]