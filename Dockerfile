
FROM python:3.9-slim

WORKDIR "/opt/app"
CMD [ "poetry", "run", "python", "/opt/app/main.py" ]

RUN set -x \
    && pip install poetry

COPY app /opt/app
RUN set -x \
    && cd /opt/app \
    && poetry install
