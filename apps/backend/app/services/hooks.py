"""Hook-text overlay drawn with FFmpeg `drawtext`.

The hook is the "opening line" that AI writes for each clip (the `hook` column).
Burning it into the first seconds of the video is what OpenShorts-style clips do
to stop the scroll.

Design choices:

* No Pillow / no extra dependency: `drawtext` ships with FFmpeg.
* Text goes through a `textfile=` instead of `text=`, so quotes, commas and
  percent signs in the hook never break the filter graph.
* `render_clip` runs FFmpeg with `cwd=settings.storage_dir`, so every path here
  is relative and colon-free (Windows drive letters would break the filter).
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

from app.core.config import settings

HOOK_MAX_LINES = 4
HOOK_MAX_LINE_CHARS = 18
HOOK_FONT_SIZE = 68
HOOK_BOX_COLOR = "black@0.6"

# Anton is the headline face shipped in storage/fonts; fall back to libass's
# default font when it is missing.
_HOOK_FONT_NAME = "Anton-Regular.ttf"


def _clean(text: str) -> str:
    """Collapse whitespace and drop control characters FFmpeg dislikes."""
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def hook_text_path(clip_id: int) -> Path:
    return settings.temp_dir / f"hook_{clip_id}.txt"


def write_hook_text(clip_id: int, text: str) -> str | None:
    """Write the wrapped hook text and return its storage-relative path.

    Returns None when there is nothing usable to draw.
    """
    cleaned = _clean(text)
    if not cleaned:
        return None

    wrapped = textwrap.wrap(cleaned, width=HOOK_MAX_LINE_CHARS)[:HOOK_MAX_LINES]
    if not wrapped:
        return None

    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    path = hook_text_path(clip_id)
    path.write_text("\n".join(wrapped), encoding="utf-8")
    return path.relative_to(settings.storage_dir).as_posix()


def _font_rel() -> str | None:
    path = settings.fonts_dir / _HOOK_FONT_NAME
    if not path.is_file():
        return None
    return path.relative_to(settings.storage_dir).as_posix()


def build_hook_filter(hook_rel: str | None, duration: float) -> str:
    """Return a `,drawtext=...` segment (leading comma, no output label)."""
    if not hook_rel:
        return ""

    safe_duration = min(max(float(duration), 0.5), 10.0)
    font_rel = _font_rel()

    parts = [
        f"textfile={hook_rel}",
        f"fontsize={HOOK_FONT_SIZE}",
        "fontcolor=white",
        "borderw=5",
        "bordercolor=black@0.85",
        "box=1",
        f"boxcolor={HOOK_BOX_COLOR}",
        "boxborderw=26",
        "line_spacing=10",
        "x=(w-text_w)/2",
        "y=h*0.09",
        f"enable='between(t,0,{safe_duration:.2f})'",
    ]
    if font_rel:
        parts.insert(0, f"fontfile={font_rel}")

    return ",drawtext=" + ":".join(parts)
