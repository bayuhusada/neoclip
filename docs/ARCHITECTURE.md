# Architecture

## Processes
- React/Vite frontend: UI only; no provider secrets.
- FastAPI backend: local REST API, validation, persistence, orchestration.
- Worker: separate process for long-running transcription/render jobs (to be implemented after foundation).
- SQLite: project/video/transcript/clip/job metadata.
- Local filesystem: original videos, extracted audio, subtitles, renders.
- faster-whisper: CPU int8 transcription initially.
- 9Router: LLM analysis through an OpenAI-compatible API, called only by backend.
- FFmpeg/FFprobe: metadata, extraction, cutting, scaling, subtitle burn-in, encoding.

## Local endpoints
- Frontend: http://127.0.0.1:5173
- Backend: http://127.0.0.1:8000
- 9Router default: http://127.0.0.1:20128/v1

## Hardware profile
AMD Ryzen 3 5300U, Radeon integrated graphics, 16 GB RAM, SSD:
- Start faster-whisper on CPU with `int8`, model `small`.
- Start with one background job and four CPU threads.
- Start FFmpeg with `libx264`; probe optional AMD AMF support (`h264_amf`) and keep CPU fallback.
- Do not assume CTranslate2/faster-whisper can use AMD GPU on Windows.
