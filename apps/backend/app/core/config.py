from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parents[1]
DEFAULT_STORAGE_DIR = REPO_ROOT / "storage"


class Settings(BaseSettings):
    app_name: str = "NeoClip AI"
    app_env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000

    storage_dir: Path = DEFAULT_STORAGE_DIR
    database_url: str = f"sqlite:///{(DEFAULT_STORAGE_DIR / 'neoclip.db').as_posix()}"

    ai_base_url: str = "http://127.0.0.1:20128/v1"
    ai_api_key: str = ""
    ai_model: str = ""
    # Chat completions for clip analysis can be slow (reasoning models, long
    # transcripts). 60s was not enough and surfaced as an empty "Cannot reach
    # AI endpoint" error because httpx timeouts have no message text.
    ai_timeout_sec: int = 300

    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    whisper_cpu_threads: int = 4
    whisper_beam_size: int = 1
    whisper_download_root: Path = DEFAULT_STORAGE_DIR / "models"

    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    video_encoder: str = "libx264"

    max_upload_mb: int = 4096
    # Optional guard rails; 0 = unlimited. ffprobe checks happen after upload, so these
    # stay loose by default instead of rejecting a valid recording mid-transfer.
    max_duration_sec: int = 0
    max_concurrent_jobs: int = 1

    # Animated captions: extra fonts for libass (allows Montserrat/Poppins/etc).
    fonts_dir: Path = DEFAULT_STORAGE_DIR / "fonts"

    # Smart framing (face detection). Model is a one-time local download.
    face_model_path: Path = DEFAULT_STORAGE_DIR / "models" / "face_detection_yunet_2023mar.onnx"
    face_sample_fps: float = 2.0
    face_max_width: int = 640
    face_confidence: float = 0.6

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def uploads_dir(self) -> Path:
        return self.storage_dir / "uploads"

    @property
    def audio_dir(self) -> Path:
        return self.storage_dir / "audio"

    @property
    def subtitles_dir(self) -> Path:
        return self.storage_dir / "subtitles"

    @property
    def clips_dir(self) -> Path:
        return self.storage_dir / "clips"

    @property
    def thumbnails_dir(self) -> Path:
        return self.storage_dir / "thumbnails"

    @property
    def temp_dir(self) -> Path:
        return self.storage_dir / "temp"


settings = Settings()
