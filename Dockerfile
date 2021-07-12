
FROM python:3.9-slim

WORKDIR "/opt/app"
CMD [ "poetry", "run", "python", "/opt/app/main.py" ]

RUN set -x \
    && pip install poetry

COPY poetry.lock pyproject.toml /opt/app/
RUN set -x \
    && cd /opt/app \
    && poetry install

COPY src /opt/app
