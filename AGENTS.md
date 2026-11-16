# NeoClip AI — OpenCode Rules

## Before changes
- Read `README.md`, `docs/PRD.md`, and `docs/ARCHITECTURE.md`.
- Inspect the existing code before creating or replacing files.
- Explain the implementation plan before large changes.
- Work in small, testable steps. Do not generate the entire product in one pass.

## Stack
- Frontend: React + Vite + JavaScript (not TypeScript) + Tailwind CSS.
- Backend: Python 3.14 + FastAPI + Pydantic + SQLAlchemy + SQLite.
- Video: FFmpeg/FFprobe.
- Transcription: faster-whisper on CPU initially.
- External LLM: 9Router via backend only.

## Security and data protection
- Never read, print, copy, expose, or modify real secrets in `.env`.
- `.env` must never be committed.
- Never put API keys in frontend code or `VITE_*` variables.
- Never delete or overwrite `storage/uploads`, `storage/clips`, `storage/models`, or database files without explicit user approval.
- Never upload videos, audio, or full transcripts to an external provider unless the user explicitly authorizes that feature.
- Bind services to `127.0.0.1` by default.
- Do not execute user-provided shell commands or concatenate untrusted input into shell commands.
- Invoke FFmpeg with argument arrays/subprocess APIs, not `shell=True`.
- Validate file extensions, MIME type, file size, paths, timestamps, and all LLM output.

## Engineering
- Keep AI providers configurable.
- Use Pydantic schemas for API input and AI JSON output.
- Long-running jobs must run in a background worker, not inside a request handler.
- Limit video/transcription concurrency to one job initially.
- Add tests for critical services and preserve working behavior.
- Avoid unnecessary dependencies and broad refactors.
- Update docs when API, database, or architecture changes.
