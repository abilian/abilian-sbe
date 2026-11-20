# Test runner image. Build context is the repo root (see compose.yaml).
FROM python:3.13-slim

RUN export DEBIAN_FRONTEND=noninteractive \
    && apt-get update -qq \
    && apt-get install -qq --no-install-recommends libmagic1 node-less poppler-utils > /dev/null \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    PATH=/app/.venv/bin:$PATH
WORKDIR /app

# Dependencies first, so editing code doesn't reinstall them.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync -q --frozen --no-group doc --extra postgres --no-install-project

COPY src src
COPY tests tests
RUN uv sync -q --frozen --no-group doc --extra postgres

CMD ["pytest", "tests"]
