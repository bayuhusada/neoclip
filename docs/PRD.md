# NeoClip AI — PRD v1.0

## Product
A single-user, local-first web app that turns long videos into short vertical clips. The app transcribes locally, asks an LLM through 9Router to propose clip ranges, then uses FFmpeg to render user-approved clips.

## MVP
1. Local dashboard and project management.
2. Upload MP4/MOV/MKV with metadata.
3. Local audio extraction and faster-whisper transcription.
4. Transcript analysis through configurable 9Router model.
5. Candidate clips with start/end, title, hook, rationale, and heuristic score.
6. Manual timestamp adjustment.
7. FFmpeg render to MP4 9:16 with subtitles.
8. Preview and download.

## Explicitly out of scope initially
- Multi-user accounts, billing, cloud storage, public deployment.
- Automatic face/speaker tracking.
- B-roll generation and social publishing.
- Guaranteed virality prediction.

## Acceptance criteria
- Upload a local video and inspect metadata.
- Generate timestamped transcript locally.
- Generate validated clip candidates through 9Router.
- Reject invalid/out-of-range timestamps.
- Render a selected clip to MP4 and preview/download it.
- Retry failed jobs without losing the source video.
