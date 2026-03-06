FROM python:3.14.3-trixie

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-workspace

COPY ./app ./app

CMD ["uv", "run", "uvicorn", "app.entrypoints.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
