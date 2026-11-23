FROM python:3.12

WORKDIR /app

RUN adduser --disabled-password --gecos '' python
RUN chown -R python:python .

COPY pyproject.toml .
COPY uv.lock .
COPY README.md .
COPY hatch_build.py .
COPY src src

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
RUN cp /root/.local/bin/uv /usr/local/bin/uv

# Install uv dependencies and build
RUN uv sync

USER python

CMD ["echo", "OK"]
