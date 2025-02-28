
FROM python:3.10-slim

WORKDIR "/opt/app"
CMD [ "poetry", "run", "python", "/opt/app/main.py" ]

RUN set -x \
    && apt-get update \
    && apt-get install \
        -y --no-install-recommends \
        ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN set -x \
    && pip install poetry

COPY poetry.lock pyproject.toml /opt/app/
RUN set -x \
    && cd /opt/app \
    && poetry install --no-root

COPY src /opt/app
