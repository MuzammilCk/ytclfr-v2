# YTCLFR Architecture

## Layers
- Domain: entities, value objects, repository contracts.
- Application: use cases and workflow orchestration.
- Infrastructure: adapters for DB, queue, OCR, AI, Spotify, external commands.
- Delivery: FastAPI API and Celery worker runtimes.

## Flow
1. API receives job.
2. Job is persisted to PostgreSQL.
3. API enqueues Celery task in Redis.
4. Worker runs video download, frame extraction, OCR, AI parse, and persistence.
5. API exposes status and knowledge endpoints.
