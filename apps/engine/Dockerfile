FROM python:3.12-slim
WORKDIR /app

# ffmpeg/ffprobe para ingesta (M3) y analisis (M4)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /bin/uv

# contracts (dependencia editable) + engine
COPY packages/contracts /app/packages/contracts
COPY apps/engine /app/apps/engine

WORKDIR /app/apps/engine
RUN uv sync --no-dev

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "vios_engine.main:app", "--host", "0.0.0.0", "--port", "8000"]
