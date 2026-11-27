FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-hin tesseract-ocr-kan && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev
COPY . .
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
