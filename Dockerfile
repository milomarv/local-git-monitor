FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update \
	&& apt-get install -y --no-install-recommends git openssh-client \
	&& rm -rf /var/lib/apt/lists/*

RUN git config --global --add safe.directory '*'

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY main.py ./
COPY templates/ ./templates/
COPY static/ ./static/

EXPOSE 8010

CMD ["uv", "run", "--no-dev", "python", "main.py"]
