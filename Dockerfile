FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY app.py ./
COPY src ./src
COPY assets ./assets
COPY data ./data

RUN useradd --system --create-home app
USER app

EXPOSE 8050
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8050/', timeout=4)"

CMD ["/app/.venv/bin/gunicorn", "app:server", "--bind", "0.0.0.0:8050", \
     "--workers", "1", "--threads", "4", "--preload", "--timeout", "60", "--access-logfile", "-"]
