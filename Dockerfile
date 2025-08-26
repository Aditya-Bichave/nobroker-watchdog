# syntax=docker/dockerfile:1.7
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates tini && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Poetry
ENV POETRY_VERSION=1.8.3
RUN curl -sSL https://install.python-poetry.org | python3 - --version ${POETRY_VERSION}
ENV PATH="/root/.local/bin:$PATH"

COPY pyproject.toml README.md ./
RUN poetry export -f requirements.txt --without-hashes -o requirements.txt && \
    pip install -r requirements.txt

COPY src ./src
COPY config.sample.yaml .
COPY run.sh .
COPY .env.example .

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["bash", "run.sh"]
