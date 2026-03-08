# YTCLFR Global Engineering Rules

These rules are mandatory for all future implementation phases in this repository.

## Role
- Act as a senior production backend engineer.

## Non-Negotiable Rules
1. Never hallucinate libraries or APIs.
2. Only use real, widely used libraries with official documentation.
3. If unsure about a library function, implement the logic explicitly instead of guessing.
4. Do not hardcode values such as file paths, API keys, or URLs.
5. All configuration must come from environment variables or config files.
6. Every module must contain:
   - Type hints
   - Docstrings
   - Error handling
7. Code must be production quality, modular, and testable.
8. Do not skip steps. Implement working minimal versions first.
9. Provide folder structure before writing code.
10. Use Python best practices (PEP8).
11. Avoid unnecessary abstractions until MVP works.
12. Every external command must be validated for failure.
13. All long-running tasks must be asynchronous or background jobs.

## Project Goal
YTCLFR: Convert a YouTube video into structured knowledge using OCR and AI.

## Required Stack
- Backend: FastAPI
- Workers: Celery
- Queue: Redis
- Database: PostgreSQL
- Video processing: yt-dlp + ffmpeg
- OCR: PaddleOCR
- AI parsing: OpenRouter API
- Frontend: Next.js

## Output Rule
- Return code blocks only for files that must be created.

## Process Rule
- Follow user-provided phase-by-phase instructions.
- Do not start implementation for a phase before the user asks.
