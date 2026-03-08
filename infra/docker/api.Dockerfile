FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir .
COPY apps ./apps
COPY packages ./packages
ENV PYTHONPATH=/app/apps/api/src:/app/packages/core/src:/app/packages/contracts/src:/app/packages/domain/src:/app/packages/application/src:/app/packages/infrastructure/src
CMD ["uvicorn", "ytclfr_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
