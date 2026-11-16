"""Render a clip to 9:16 MP4 with burned-in subtitles.

FFmpeg is always invoked with an argument list (never `shell=True`). The
`subtitles` filter needs a path that survives FFmpeg's own filter escaping, so
FFmpeg runs with `cwd=settings.storage_dir` and receives a relative, forward-slash
path (e.g. `subtitles/12.srt`). That avoids Windows drive-letter colons entirely.
"""

import subprocess
from pathlib import Path

from app.core.config import settings
from app.services.framing import build_framing_filter, build_split_filter
from app.services.hooks import build_hook_filter

RENDER_TIMEOUT_SECONDS = 1800  # 30 min; a 60 s 1080x1920 encode is far below this
OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920

# `force_style` values must not contain commas outside the quoted string.
_SUBTITLE_STYLES = {
    "clean": "FontName=DejaVu Sans,FontSize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,MarginV=60,Alignment=2",
    "bold": "FontName=DejaVu Sans,FontSize=24,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=4,Shadow=1,MarginV=140,Alignment=2",
    "blur": "FontName=DejaVu Sans,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,MarginV=90,Alignment=2",
}

TEMPLATES = tuple(_SUBTITLE_STYLES)
DEFAULT_TEMPLATE = "clean"


class RenderError(RuntimeError):
    """Raised when FFmpeg refuses to render the clip."""


def normalize_template(template: str | None) -> str:
    """Unknown templates fall back to the default instead of failing a render."""
    if template in _SUBTITLE_STYLES:
        return template  # type: ignore[return-value]
    return DEFAULT_TEMPLATE


def _subtitle_filter(subtitle_rel: str | None, template: str) -> str:
    if not subtitle_rel:
        return ""
    style = _SUBTITLE_STYLES[template]
    return f",subtitles=filename={subtitle_rel}:force_style='{style}'"


def _ass_filter(ass_rel: str | None) -> str:
    """ASS filter with custom fontsdir (SIL OFL fonts in storage/fonts)."""
    if not ass_rel:
        return ""
    fonts_rel = ""
    fonts_dir = settings.fonts_dir
    if fonts_dir.is_dir():
        fonts_rel = f":fontsdir={fonts_dir.relative_to(settings.storage_dir).as_posix()}"
    return f",ass={ass_rel}{fonts_rel}"


def build_filter(
    template: str,
    subtitle_rel: str | None = None,
    ass_rel: str | None = None,
    framing: list | None = None,
    video_w: int = 0,
    video_h: int = 0,
    framing_split: tuple | None = None,
    split_stacked: bool = False,
    hook_rel: str | None = None,
    hook_duration: float = 3.0,
) -> str:
    """Return the filter graph for the given template.

    `ass_rel` takes priority over `subtitle_rel` (animated captions win).
    `clean`/`bold`: scale up and center-crop to 1080x1920.
    `blur`: same blurred background, original frame centered on top.

    When `framing` is a non-empty keyframe list (source-pixel coords), the
    framing crop (`crop=cw:ch:x='..':y='..'`) + scale 9:16 graph is used instead.
    `framing_split` (left_keyframes, right_keyframes) builds a split screen.
    `split_stacked=True` builds a top/bottom split (vstacked bands),
    otherwise a side-by-side split (hstacked strips).
    `hook_rel` is a storage-relative text file burned in for the first
    `hook_duration` seconds.
    `video_w`/`video_h` are required for framing to compute the crop size.
    """
    template = normalize_template(template)
    overlay = _ass_filter(ass_rel) or _subtitle_filter(subtitle_rel, template)
    overlay += build_hook_filter(hook_rel, hook_duration)

    if framing_split and video_w > 0 and video_h > 0:
        left, right = framing_split
        split = build_split_filter(left, right, video_w, video_h, stacked=split_stacked)
        return f"{split}{overlay}[v]"

    if framing and video_w > 0 and video_h > 0:
        # Smart framing: crop per face keyframe then scale to 9:16.
        framed = build_framing_filter(framing, video_w, video_h)
        if template == "blur":
            # Blurred full-frame background + framed subject centered on top, so
            # the blur stays visible around the subject (template stays meaningful).
            fg_w = int(OUTPUT_WIDTH * 0.74) // 2 * 2
            return (
                f"[0:v]scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=increase,"
                f"crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT},boxblur=24:5[bg];"
                f"[0:v]{framed},scale={fg_w}:-2[fg];"
                "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1"
                f"{overlay}[v]"
            )
        return f"[0:v]{framed}{overlay}[v]"

    if template == "blur":
        return (
            f"[0:v]scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT},boxblur=20:5[bg];"
            "[0:v]scale=1080:-2:force_original_aspect_ratio=decrease[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1"
            f"{overlay}[v]"
        )

    return (
        f"[0:v]scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT},setsar=1"
        f"{overlay}[v]"
    )


def render_clip(
    video_path: Path,
    output_path: Path,
    start_sec: float,
    end_sec: float,
    subtitle_rel: str | None = None,
    template: str = DEFAULT_TEMPLATE,
    encoder: str | None = None,
    ass_rel: str | None = None,
    framing: list | None = None,
    video_w: int = 0,
    video_h: int = 0,
    framing_split: tuple | None = None,
    split_stacked: bool = False,
    hook_rel: str | None = None,
    hook_duration: float = 3.0,
) -> Path:
    """Cut `start_sec`-`end_sec` out of `video_path` and write a 9:16 MP4.

    `subtitle_rel`/`ass_rel` are relative to `settings.storage_dir`.
    `framing` is an optional list of crop keyframes (source-pixel coords, e.g.
    [{"t": 0.0, "x": ..., "y": ..., "zoom": ...}]) for smart face-follow framing.
    `framing_split` is an optional (left, right) pair of keyframe lists for a
    split screen (takes precedence over `framing`).
    `split_stacked` determines if split screen is top/bottom (True) or side/side (False).
    `video_w`/`video_h` are the source dimensions used to compute the crop size.
    """
    duration = end_sec - start_sec
    if duration <= 0:
        raise RenderError("Durasi klip tidak valid (end_sec harus > start_sec).")
    if not video_path.exists():
        raise RenderError(f"File video tidak ditemukan: {video_path.name}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        settings.ffmpeg_path,
        "-y",
        "-ss",
        f"{start_sec:.3f}",
        "-i",
        str(video_path),
        "-t",
        f"{duration:.3f}",
        "-filter_complex",
        build_filter(
            template,
            subtitle_rel=subtitle_rel,
            ass_rel=ass_rel,
            framing=framing,
            video_w=video_w,
            video_h=video_h,
            framing_split=framing_split,
            split_stacked=split_stacked,
            hook_rel=hook_rel,
            hook_duration=hook_duration,
        ),
        "-map",
        "[v]",
        "-map",
        "0:a?",
        "-c:v",
        encoder or settings.video_encoder,
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            timeout=RENDER_TIMEOUT_SECONDS,
            check=False,
            cwd=str(settings.storage_dir),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RenderError(f"ffmpeg tidak bisa dijalankan: {exc}") from exc

    if completed.returncode != 0:
        stderr = completed.stderr.decode(errors="replace").strip()
        raise RenderError(f"Render gagal: {stderr[-500:]}")

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RenderError("Render selesai tetapi file output kosong.")

    return output_path


def render_thumbnail(
    video_path: Path,
    output_path: Path,
    at_sec: float,
    width: int = 360,
) -> Path:
    """Grab one frame at `at_sec` as a JPEG thumbnail."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        settings.ffmpeg_path,
        "-y",
        "-ss",
        f"{max(at_sec, 0.0):.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-vf",
        f"scale={width}:-2",
        "-q:v",
        "4",
        str(output_path),
    ]
    try:
        completed = subprocess.run(
            command, capture_output=True, timeout=120, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RenderError(f"ffmpeg tidak bisa dijalankan: {exc}") from exc

    if completed.returncode != 0 or not output_path.exists():
        stderr = completed.stderr.decode(errors="replace").strip()
        raise RenderError(f"Thumbnail gagal: {stderr[-300:]}")
    return output_path
