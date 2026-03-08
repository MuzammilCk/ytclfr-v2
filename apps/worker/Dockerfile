FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir .
COPY . .
CMD ["celery", "-A", "ytclfr_worker.worker:celery_app", "worker", "--loglevel=INFO"]
