FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TIKTOKEN_CACHE_DIR=/opt/tiktoken
WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
COPY prompts ./prompts
RUN pip install --no-cache-dir . \
    && mkdir -p /opt/tiktoken \
    && python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')" \
    && pip freeze > /app/installed-dependencies.txt \
    && groupadd -g 10001 dodam && useradd -u 10001 -g dodam -m dodam \
    && mkdir -p /data/object-storage && chown dodam:dodam /data/object-storage
USER 10001:10001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8006", "--workers", "1"]
