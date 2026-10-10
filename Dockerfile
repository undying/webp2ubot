
FROM python:3.11-slim

WORKDIR "/opt/app"
CMD [ "poetry", "run", "python", "/opt/app/main.py" ]

ARG DENO_VERSION=v2.9.7

RUN set -x \
    && apt-get update \
    && apt-get install \
        -y --no-install-recommends \
        ffmpeg ca-certificates curl unzip \
    && case "$(dpkg --print-architecture)" in \
        amd64) DENO_TARGET=x86_64-unknown-linux-gnu ;; \
        arm64) DENO_TARGET=aarch64-unknown-linux-gnu ;; \
        *) echo "unsupported architecture" && exit 1 ;; \
       esac \
    && curl -fsSL -o /tmp/deno.zip \
        "https://github.com/denoland/deno/releases/download/${DENO_VERSION}/deno-${DENO_TARGET}.zip" \
    && unzip -q /tmp/deno.zip -d /usr/local/bin \
    && chmod +x /usr/local/bin/deno \
    && rm /tmp/deno.zip \
    && apt-get purge -y curl unzip \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN set -x \
    && pip install poetry

COPY poetry.lock pyproject.toml /opt/app/
RUN set -x \
    && cd /opt/app \
    && poetry install --no-root

COPY src /opt/app
