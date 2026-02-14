FROM python:3.14.3-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/


WORKDIR /smart-routing-platform

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-workspace

COPY . /smart-routing-platform

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
