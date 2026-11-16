# NeoClip AI — Local Starter

Local-first personal AI video clipper. This repository is the initial foundation, not a finished video editor.

## Recommended environment (Windows)
- Python 3.14.x (64-bit)
- Node.js 22 LTS
- FFmpeg + FFprobe available on PATH
- 9Router running locally (default OpenAI-compatible base URL: `http://127.0.0.1:20128/v1`)
- 16 GB RAM; transcription starts on CPU with faster-whisper `small` / `int8`

## 1. Backend
Open PowerShell in `apps/backend`:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

`alembic upgrade head` creates `storage/neoclip.db`. `.env` uses absolute paths for
`DATABASE_URL`, `STORAGE_DIR`, and `WHISPER_DOWNLOAD_ROOT` so behavior does not depend
on the current working directory.

### Tests

```powershell
.\.venv\Scripts\pytest.exe
```

### Schema changes

```powershell
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## 5. API (current)

| Method | Path | Keterangan |
|---|---|---|
| GET | `/api/health` | status ffmpeg/ffprobe/storage |
| GET | `/api/config` | konfigurasi aktif tanpa API key (termasuk batas upload) |
| GET | `/api/settings/ai` | kredensial AI tersimpan (key tersamar `****1234`) |
| POST | `/api/settings/ai` | simpan `{base_url, api_key?, model?}` ke `storage/ai_config.json` |
| POST | `/api/settings/ai/test` | uji `GET {base}/v1/models`, balikan latensi + daftar model |
| POST | `/api/settings/ai/quota` | coba endpoint billing OpenAI (`subscription` + `usage`) |
| POST | `/api/projects` | `{name, description?}` |
| GET | `/api/projects` | daftar project |
| GET/PATCH/DELETE | `/api/projects/{id}` | detail / ubah / hapus + file video |
| POST | `/api/videos` | multipart: `project_id`, `file` (MP4/MOV/MKV) |
| GET | `/api/videos?project_id=` | daftar video |
| GET/DELETE | `/api/videos/{id}` | detail / hapus video + file |
| POST | `/api/videos/{id}/transcribe` | antre transkripsi (202 job baru, 200 bila sudah ada) |
| POST | `/api/videos/{id}/transcribe?force=true` | antre transkripsi ulang (re-generate word-level timestamps) |
| GET | `/api/videos/{id}/transcript` | transkrip tersimpan (404 bila belum) |
| GET | `/api/videos/{id}/jobs` | status job untuk polling UI |
| POST | `/api/videos/{id}/analyze` | antre analisis AI (202; 409 bila belum ada transkrip) |
| GET | `/api/videos/{id}/clips` | kandidat klip, urut skor |
| PATCH | `/api/clips/{id}` | ubah judul/hook/rentang/skor/status (`candidate`/`approved`) + `template` (`clean`/`bold`/`blur`) + `caption_preset` (`modern_bold`/`karaoke`/`minimal`/`podcast`/`hormozi`/`classic`/`anton`/`pill`/`oneword`) + `caption_size` (font multiplier `0.6`–`1.8`, default `1.0`) + `camera_mode` (`original`/`smart_auto`/`single`/`split`/`split_stacked`/`group`/`auto_speaker`/`dynamic_zoom`) + `hook_enabled`/`hook_duration` |
| DELETE | `/api/clips/{id}` | hapus klip + file output/subtitle |
| POST | `/api/clips/{id}/render` | antre render 9:16 + subtitle (202; 409 bila belum `approved`) |
| GET | `/api/clips/{id}/video` | stream file hasil render MP4 |
| GET | `/api/clips/{id}/thumbnail` | thumbnail JPEG (auto-generate via FFmpeg) |
| GET | `/api/clips/{id}/framing` | framing cache/keyframes + camera_mode |
| PUT | `/api/clips/{id}/framing` | simpan manual camera_mode + keyframes |
| POST | `/api/clips/{id}/framing/regenerate` | deteksi ulang + generate framing keyframes (by force refresh) |

Upload memvalidasi ekstensi, MIME, dan `MAX_UPLOAD_MB`, menyimpan ke `storage/uploads`,
lalu mengisi metadata lewat `ffprobe`. Video tanpa stream video ditandai `failed`.
Frontend memanggil lewat proxy Vite `/api` → `http://127.0.0.1:8000`.

### Batas upload

| Batas | Default | Diatur lewat | Kapan dicek |
|---|---|---|---|
| Ukuran file | 4096 MB (4 GB) | `MAX_UPLOAD_MB` | saat streaming, ditolak 413 di tengah upload |
| Durasi video | 0 = tanpa batas | `MAX_DURATION_SEC` | setelah `ffprobe`, file dihapus + 413 |
| Format | `.mp4`, `.mov`, `.mkv` | `ALLOWED_EXTENSIONS` di `services/files.py` | sebelum file ditulis |
| MIME | `video/mp4`, `video/quicktime`, `video/x-matroska`, `video/mpeg`, `application/octet-stream` | `ALLOWED_MIME_TYPES` | sebelum file ditulis |

Default 4 GB cukup untuk sekitar 2 jam rekaman 4 Mbps. Durasi dibiarkan tak terbatas
karena ffprobe baru bisa mengukur setelah upload selesai; set `MAX_DURATION_SEC=3600`
kalau ingin membatasi 1 jam. Batas aktif ditampilkan di kartu upload (Dashboard),
halaman Settings, dan `GET /api/config` (`max_upload_mb`, `max_duration_sec`,
`allowed_extensions`, `allowed_mime_types`).

Transkripsi berjalan di worker thread (1 job sekaligus). Model `small` int8 diunduh
sekali ke `storage/models` (~464 MB). `av` dipin ke `16.1.0` karena PyAV 17+ menghapus
`metadata_errors` yang masih dipakai faster-whisper 1.2.1.

UI mendukung polling progres otomatis, penanganan video tanpa audio, dan tampilan transkrip
per segmen dengan timestamp.

## 6. Render pipeline

Render hasil 9:16 MP4 dengan subtitle terbakar (burned-in). Tiga template:
- **clean** — crop center ke 1080×1920, subtitle putih tipis.
- **bold** — subtitle tebal dengan border & bayangan, margin bawah besar.
- **blur** — background blur efek + subtitle putih tipis.

Setiap klip menyimpan `template` (`clean`/`bold`/`blur`) di DB. Tiap kali
dirender, SRT dibuat ulang dari transkrip segmen sehingga edit rentang (start/end)
selalu tercermin dalam burned-in teks. File output `clips/<id>.mp4`, subtitle
`srt` berada di `storage/subtitles/<id>.srt`.

Rute API:
- `POST /api/clips/{id}/render` (antre job; status klip harus `approved`).
- `GET /api/clips/{id}/video` (stream output MP4).
- `GET /api/clips/{id}/thumbnail` (ambar frame JPEG).

Workflow dari UI: pilih video → **Analisis AI** → periksa kandidat → **Setujui** klip →
klik **Render 9:16** → polling progres → **Download MP4** setelah selesai.
Setelah render, klip bisa diputar inline & diunduh.

### Smart framing (Phase 2)

**Camera modes** (`camera_mode` di PATCH `/api/clips/{id}`):
- `smart_auto` (default klip baru) — otomatis memilih mode per klip:
  - 2 orang mengobrol sepanjang klip → **split screen**
  - 1 orang berbicara → **fokus 1 orang**
  - banyak wajah / tawa grup → **group** (bingkai melebar menampung semua)
- `original` — tanpa framing tambahan (crop tengah), tidak memicu deteksi wajah.
- `single` — fokus pada satu wajah dominan.
- `split` — split screen 2 wajah (kiri/kanan 540×1920, `hstack`).
- `group` — bingkai mengikuti gabungan semua wajah.
- `auto_speaker` — ikuti wajah dominan (sama seperti single).
- `dynamic_zoom` — zoom halus ke subjek.

Setelah render, `framing_mode` menyimpan mode efektif hasil `smart_auto`
(`split`/`single`/`group`) dan ditampilkan sebagai badge "Kamera:" di UI.

Framing API:
- `GET /api/clips/{id}/framing` — keyframes + `resolved_mode` + `split` preview.
- `PUT /api/clips/{id}/framing` — simpan `{camera_mode, keyframes?}` (manual override).
- `POST /api/clips/{id}/framing/regenerate` — deteksi wajah baru + generate ulang.

Deteksi wajah berjalan di backend saja; video tidak meninggalkan mesin. Model
`face_detection_yunet_2023mar.onnx` di `storage/models/`. Deteksi 2 fps, cache di
`storage/face_cache/`. Framing dievaluasi per frame di FFmpeg (`crop=x:y`), output
selalu 1080×1920. Template `blur` tetap berfungsi: background blur + subjek framed
di tengah.

**Batasan jujur:** "siapa yang bicara" tidak ditentukan dari audio; `smart_auto`
memakai jumlah wajah per detik sebagai proxy. Override manual lewat `camera_mode`
atau keyframes.

### Penanganan respons AI

`analyzer.py` menangani model campuran di 9Router:
- `message.content` → `reasoning_content` (DeepSeek-R1) → `reasoning` (QwQ) →
  `tool_calls[].function.arguments`. Model reasoning yang menaruh JSON di field
  reasoning tetap terbaca.
- Retry otomatis dengan `max_tokens` 2× jika `finish_reason == "length"`.
- Error actionable: pesan menyebut `finish_reason` + saran ganti model (hindari
  reasoning model atau naikkan `MAX_OUTPUT_TOKENS`) bila content kosong.


## 6. UI upload

Dashboard (`src/views/DashboardView.jsx`) sudah berisi:
- `UploadCard` — drag & drop / pilih file, progress bar (XHR), form buat project bila belum ada, ringkasan metadata setelah selesai.
- `VideoList` — daftar video + status (`ready`/`failed`/`probing`) + durasi/resolusi/fps/codec/ukuran, tombol transkrip dan hapus.
- Statistik dashboard dihitung dari data nyata (jumlah project & video).

Navigasi sidebar sekarang berpindah view tanpa reload:
- **Dashboard** — upload, statistik, daftar video.
- **My Projects** — grid project, buat/edit/hapus, detail project + video.
- **AI Clip Editor** — pilih video, tombol **Analisis AI** (job `analyze`), progress polling,
  lalu daftar kandidat klip: judul/hook/start/end bisa diedit, **Setujui** / **Batalkan** / **Hapus**.
  Transkrip dikirim ke 9Router lewat backend saja.
- **Settings** — isi Base URL / API key / Model 9Router langsung dari UI, tombol **Save**,
  **Test koneksi**, **Cek kuota**, plus panduan "Cara dapat API key". Status
  API/FFmpeg/Whisper/9Router/storage tampil di kartu terpisah.

Hapus video/project memakai dialog konfirmasi dan menghapus file di disk (upload, WAV cache,
output klip) lewat `DELETE`. Path dari DB divalidasi agar tetap di dalam `storage/`.




Open:
- API: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/api/health

## 2. Frontend
Open another PowerShell in `apps/frontend`:

```powershell
npm install
npm run dev
```

Open the local URL printed by Vite (normally http://localhost:5173).

## 3. FFmpeg
Install an FFmpeg Windows build and add its `bin` directory to PATH. Verify:

```powershell
ffmpeg -version
ffprobe -version
```

## 4. 9Router
Two ways to set credentials:

1. **UI (dipakai sehari-hari)** — buka **Settings → 9Router / AI**, isi Base URL
   (`http://127.0.0.1:20128`), API key, dan Model, lalu **Save**. Nilai disimpan di
   `storage/ai_config.json`. Tombol **Test koneksi** memanggil `GET {base}/v1/models`
   lewat backend dan menampilkan latensi + daftar model.
2. **`.env` (bootstrap / fallback)** — `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`.
   Nilai di `storage/ai_config.json` menang atas `.env`; `.env` hanya dipakai kalau
   file JSON belum punya nilai untuk field tersebut.

Keep 9Router on the same PC. Do not put the key in React/Vite environment variables. The browser
must never receive the secret; `GET /api/settings/ai` only returns a masked value (`****1234`).

Cara dapat API key 9Router: jalankan 9Router → buka
`http://127.0.0.1:20128/dashboard/endpoint` → bagian **API Keys** (otomatis ada
"Default Key") → **Create Key**, beri nama, copy key `sk-...` → tempel di Settings.
Provider upstream (Gemini, Claude, dst.) didaftarkan di dashboard 9Router, bukan di NeoClip.

**Kuota:** tombol **Cek kuota** hanya berfungsi untuk endpoint yang menyediakan
`/dashboard/billing/subscription` + `/dashboard/billing/usage` (format OpenAI). 9Router
tidak menyediakannya, jadi hasilnya `{"available": false}` dengan pesan jelas. Kuota
per-provider milik 9Router ada di `http://127.0.0.1:20128/dashboard/quota` dan butuh
session login dashboard, jadi tidak dibaca dari backend NeoClip.

## Feature updates & notes

- **Caption presets:** baru: `anton` (warna kuning hero), `pill` (kotak ungu di belakang), `oneword` (satu kata per cue). Semua preset tinggi margin aman dari UI bottom (340–420) di canvas 1080x1920.
- **Camera mode:** `split_stacked` (split atas-bawah, 2 band 1080×960) sebagai alternatif side-by-side. Tampil di UI.
- **Hook overlay:** kolom `hook_enabled` / `hook_duration` di API; teks hook dibakar di bagian awal pakai FFmpeg `drawtext` (tanpa dependency baru).

**Fitur ditunda** (masih menunggu model visi / Gemini):
- Deteksi active-speaker lewat movement mulut (OpenShorts).
- Deteksi subtitle yang sudah dibakar ke video (burned-subtitle detection).
- Layout picker berbasis AI (pilih layout di antara TRACK / GENERAL / SPLIT / SCREENCAST).

## Hardware profile
- faster-whisper: CPU, `int8`, model `small`, one transcription job at a time.
- CPU threads: start at 4; reduce to 2 if the PC becomes unresponsive.
- FFmpeg: start with `libx264` software encoding for reliability.
- AMD AMF (`h264_amf`) is optional: test whether the installed FFmpeg build and AMD driver expose it before enabling it. Always retain a `libx264` fallback.

## Important
- `storage/`, `.env`, model weights, source videos and rendered clips are private local data.
- Do not commit secrets or user media.
- Do not expose the backend beyond localhost without adding authentication and a security review.
