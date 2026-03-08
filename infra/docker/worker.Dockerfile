FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir .
COPY apps ./apps
COPY packages ./packages
ENV PYTHONPATH=/app/apps/worker/src:/app/packages/core/src:/app/packages/contracts/src:/app/packages/domain/src:/app/packages/application/src:/app/packages/infrastructure/src
CMD ["celery", "-A", "ytclfr_worker.worker:celery_app", "worker", "--loglevel=INFO"]
