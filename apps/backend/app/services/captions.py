"""Generate ASS (Advanced SubStation Alpha) subtitles with word-level animation presets.

Supports 6 presets:
- modern_bold: Montserrat ExtraBold, Pop animation, highlighted active word.
- karaoke: Montserrat Bold, Smooth sweep highlight (\kf).
- minimal: Poppins SemiBold, Soft fade-in, clean look.
- podcast: Poppins Bold, Slide-up effect, strong contrast.
- hormozi: Montserrat ExtraBold, Large pop, bright yellow active word.
- classic: DejaVu Sans, Standard subtitle without word highlights.
"""

from typing import Any, List, Dict
import math

# Default fallback font
FALLBACK_FONT = "DejaVu Sans"

# Presets configuration
# Sizes are in ASS script units for a 1080x1920 canvas (PlayResY=1920), so a
# value of ~88 renders ~88/1920 = 4.6% of the frame height. Anything under ~50
# is unreadable on a phone screen.
PRESETS = {
    "modern_bold": {
        "font": "Montserrat",
        "size": 88,
        "primary": "&H00FFFFFF",  # White
        "active": "&H0000FFFF",   # Yellow
        "outline_color": "&H00000000", # Black
        "outline": 8,
        "shadow": 3,
        "align": 2, # Bottom Center
        "margin_v": 380,
        "anim": "pop"
    },
    "karaoke": {
        "font": "Montserrat",
        "size": 80,
        "primary": "&H00FFFFFF",
        "active": "&H0000FF00",   # Green
        "outline_color": "&H00000000",
        "outline": 6,
        "shadow": 0,
        "align": 2,
        "margin_v": 380,
        "anim": "karaoke"
    },
    "minimal": {
        "font": "Poppins",
        "size": 64,
        "primary": "&H00E0E0E0",  # Soft White
        "active": "&H00FFFFFF",
        "outline_color": "&H00222222",
        "outline": 3,
        "shadow": 0,
        "align": 2,
        "margin_v": 340,
        "anim": "fade"
    },
    "podcast": {
        "font": "Poppins",
        "size": 82,
        "primary": "&H00FFFFFF",
        "active": "&H00FFAA00",   # Orange
        "outline_color": "&H00000000",
        "outline": 8,
        "shadow": 4,
        "align": 2,
        "margin_v": 400,
        "anim": "slide"
    },
    "hormozi": {
        "font": "Montserrat",
        "size": 104,
        "primary": "&H00FFFFFF",
        "active": "&H0000FFFF",   # Bright Yellow
        "outline_color": "&H00000000",
        "outline": 10,
        "shadow": 5,
        "align": 2,
        "margin_v": 420,
        "anim": "hormozi_pop"
    },
    "classic": {
        "font": "DejaVu Sans",
        "size": 56,
        "primary": "&H00FFFFFF",
        "active": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "outline": 4,
        "shadow": 0,
        "align": 2,
        "margin_v": 340,
        "anim": "none"
    },
    # OpenShorts-inspired looks (Anton headline, box behind text)
    "anton": {
        "font": "Anton",
        "size": 96,
        "primary": "&H00FFFFFF",   # White
        "active": "&H0000E5FF",    # Yellow (#FFE500)
        "outline_color": "&H00000000",
        "outline": 5,
        "shadow": 0,
        "align": 2,
        "margin_v": 400,           # keep clear of TikTok/Reels bottom UI
        "anim": "pop",
        "uppercase": True,
        "bold": False,
        "max_chars": 16,
    },
    "pill": {
        "font": "Montserrat",
        "size": 88,
        "primary": "&H00FFFFFF",
        "active": "&H0000E5FF",    # text stays white on purple box below
        "outline_color": "&H00ED3A7C",  # #7C3AED border (BGR)
        "outline": 6,
        "shadow": 0,
        "align": 2,
        "margin_v": 400,
        "anim": "pop",
        "uppercase": True,
        "border_style": 3,
        "max_chars": 9,
    },
    "oneword": {
        "font": "Anton",
        "size": 110,
        "primary": "&H00FFFFFF",
        "active": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "outline": 6,
        "shadow": 0,
        "align": 2,
        "margin_v": 400,
        "anim": "pop",
        "uppercase": True,
        "bold": False,
        "words_per_cue": 1,
    },
}

# Per-clip text-size multiplier limits (persisted on the clip).
MIN_SIZE_SCALE = 0.6
MAX_SIZE_SCALE = 1.8


def clamp_size_scale(value: float | None) -> float:
    """Clamp a stored per-clip font scale into the supported range."""
    if value is None:
        return 1.0
    try:
        scale = float(value)
    except (TypeError, ValueError):
        return 1.0
    return min(max(scale, MIN_SIZE_SCALE), MAX_SIZE_SCALE)


def _split_lines(words: List[Dict[str, Any]], max_chars: int) -> List[List[Dict[str, Any]]]:
    """Wrap words into lines that fit `max_chars` characters."""
    lines: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    length = 0
    for word in words:
        text = word["text"]
        extra = len(text) + (1 if current else 0)
        if current and length + extra > max_chars:
            lines.append(current)
            current = [word]
            length = len(text)
        else:
            current.append(word)
            length += extra
    if current:
        lines.append(current)
    return lines


def _chunk_words(
    words: List[Dict[str, Any]],
    max_chars: int,
    max_lines: int = 2,
    words_per_cue: int | None = None,
) -> List[List[Dict[str, Any]]]:
    """Group words into cues holding at most `max_lines` wrapped lines.

    Keeps large fonts from overflowing the 1080px frame: instead of a fixed
    4-word chunk, cues break on a character budget derived from font size.
    `words_per_cue` overrides that with a hard word count (the `oneword` look).
    """
    if words_per_cue and words_per_cue > 0:
        return [words[i:i + words_per_cue] for i in range(0, len(words), words_per_cue)]

    cues: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    for word in words:
        trial = current + [word]
        if current and len(_split_lines(trial, max_chars)) > max_lines:
            cues.append(current)
            current = [word]
        else:
            current = trial
    if current:
        cues.append(current)
    return cues

def _ass_time(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    cs = int(round(seconds * 100)) # centiseconds
    m, cs = divmod(cs, 100)
    h, m = divmod(m, 3600)
    m, s = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

def _estimate_word_timestamps(segment: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Fallback if whisper didn't produce word-level timestamps."""
    text = segment.get("text", "").strip()
    if not text:
        return []
    
    words = text.split()
    if not words:
        return []

    start = float(segment.get("start", 0.0))
    end = float(segment.get("end", 0.0))
    duration = max(0.1, end - start)
    
    # Calculate length of characters to distribute time proportionally
    total_chars = sum(len(w) for w in words)
    if total_chars == 0:
        return []

    res = []
    curr = start
    for w in words:
        w_len = len(w)
        w_dur = (w_len / total_chars) * duration
        res.append({
            "start": round(curr, 2),
            "end": round(curr + w_dur, 2),
            "text": w,
            "estimated": True
        })
        curr += w_dur
    return res

def build_ass(
    segments: List[Dict[str, Any]],
    start_sec: float,
    end_sec: float,
    preset_name: str = "modern_bold",
    play_res_x: int = 1080,
    play_res_y: int = 1920,
    size_scale: float = 1.0,
) -> tuple[str, int, bool]:
    """Build complete ASS subtitle content for a given clip window.

    `size_scale` multiplies the preset font size (and its outline/shadow) so the
    UI can offer a "text size" slider without editing presets.

    Returns: (ass_content, cue_count, has_estimated_timestamps)
    """
    preset = PRESETS.get(preset_name, PRESETS["modern_bold"])
    has_estimated = False

    scale = clamp_size_scale(size_scale)
    font_size = max(12, int(round(preset["size"] * scale)))
    outline = max(1, int(round(preset["outline"] * scale)))
    shadow = max(0, int(round(preset["shadow"] * scale)))
    margin_v = preset["margin_v"]
    margin_h = max(30, int(round(play_res_x * 0.055)))  # 60 px at 1080 wide
    border_style = preset.get("border_style", 1)
    bold = -1 if preset.get("bold", True) else 0
    upper = bool(preset.get("uppercase", False))

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{preset['font']},{font_size},{preset['primary']},&H000000FF,{preset['outline_color']},&H80000000,{bold},0,0,0,100,100,0,0,{border_style},{outline},{shadow},{preset['align']},{margin_h},{margin_h},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # Rough average glyph width for a bold sans face: 0.55 x font size.
    # Keep ~92% of the frame width usable for text.
    usable_w = play_res_x * 0.92
    preset_chars = preset.get("max_chars")
    if preset_chars:
        # Preset budgets are tuned for the preset size; bigger text needs fewer
        # characters per line or it runs off the 1080px frame.
        max_chars = max(4, int(preset_chars / max(scale, 0.1)))
    else:
        max_chars = max(10, int(usable_w / (font_size * 0.55)))

    def _txt(word: Dict[str, Any]) -> str:
        return word["text"].upper() if upper else word["text"]

    lines = []
    cue_count = 0

    # Filter & process segments in clip window
    for seg in segments:
        seg_start = float(seg.get("start", 0))
        seg_end = float(seg.get("end", 0))

        # Clamp segment to clip boundaries
        c_start = max(seg_start, start_sec)
        c_end = min(seg_end, end_sec)

        if c_end <= c_start:
            continue

        # Shift timestamps relative to clip start
        rel_start = c_start - start_sec
        rel_end = c_end - start_sec

        # Extract words or fallback
        words = seg.get("words")
        if not words:
            words = _estimate_word_timestamps(seg)
            if words:
                has_estimated = True

        if not words:
            # Fallback to plain segment text if no words available
            text = seg.get("text", "").strip()
            if text:
                if upper:
                    text = text.upper()
                start_str = _ass_time(rel_start)
                end_str = _ass_time(rel_end)
                lines.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text}")
                cue_count += 1
            continue

        # Filter words within this clamped window
        valid_words = []
        for w in words:
            w_s = float(w.get("start", 0))
            w_e = float(w.get("end", 0))
            if w_e > start_sec and w_s < end_sec:
                valid_words.append({
                    "start": max(0.0, w_s - start_sec),
                    "end": min(end_sec - start_sec, w_e - start_sec),
                    "text": w.get("text", "").strip()
                })

        if not valid_words:
            continue

        # Group into at most 2 wrapped lines so big fonts stay inside the frame.
        words_per_cue = preset.get("words_per_cue")
        anim_type = preset["anim"]
        max_lines = 2
        for cue in _chunk_words(
            valid_words, max_chars, max_lines=max_lines, words_per_cue=words_per_cue
        ):
            wrapped = _split_lines(cue, max_chars)
            line_start = cue[0]["start"]
            line_end = cue[-1]["end"]

            if anim_type in ("pop", "hormozi_pop"):
                scale_up = 120 if anim_type == "hormozi_pop" else 110
                # Highlight one word at a time, preserving line breaks.
                flat_idx = 0
                for active_w in cue:
                    rendered = []
                    cursor = 0
                    for line in wrapped:
                        parts = []
                        for w in line:
                            if cursor == flat_idx:
                                c_tag = f"\\c{preset['active']}"
                                anim_tag = (
                                    f"\\t(0,100,\\fscx{scale_up}\\fscy{scale_up})"
                                    "\\t(100,200,\\fscx100\\fscy100)"
                                )
                                parts.append(f"{{{c_tag}{anim_tag}}}{_txt(w)}{{\\r}}")
                            else:
                                parts.append(_txt(w))
                            cursor += 1
                        rendered.append(" ".join(parts))

                    lines.append(
                        f"Dialogue: 0,{_ass_time(active_w['start'])},{_ass_time(active_w['end'])},"
                        f"Default,,0,0,0,,{'\\N'.join(rendered)}"
                    )
                    cue_count += 1
                    flat_idx += 1

            elif anim_type == "karaoke":
                # Single cue with ASS \kf sweep, line breaks preserved.
                rendered = []
                cursor = 0
                for line in wrapped:
                    parts = []
                    for w in line:
                        dur_cs = max(1, int(round((w["end"] - w["start"]) * 100)))
                        parts.append(f"{{\\kf{dur_cs}}}{_txt(w)}")
                        cursor += 1
                    rendered.append(" ".join(parts))

                lines.append(
                    f"Dialogue: 0,{_ass_time(line_start)},{_ass_time(line_end)},"
                    f"Default,,0,0,0,,{'\\N'.join(rendered)}"
                )
                cue_count += 1

            elif anim_type == "oneword":
                # One big word at a time (OpenShorts "oneword" look).
                for w in cue:
                    lines.append(
                        f"Dialogue: 0,{_ass_time(w['start'])},{_ass_time(w['end'])},"
                        f"Default,,0,0,0,,{_txt(w)}"
                    )
                    cue_count += 1

            else:
                # none / fade / slide: plain line, optional soft animation.
                text = "\\N".join(" ".join(_txt(w) for w in line) for line in wrapped)
                if anim_type == "fade":
                    text = f"{{\\fad(150,150)}}{text}"
                elif anim_type == "slide":
                    # Rise into place just above the platform's bottom UI.
                    y_end = max(0, play_res_y - margin_v)
                    y_start = y_end + 85
                    text = (
                        f"{{\\move({play_res_x // 2},{y_start},"
                        f"{play_res_x // 2},{y_end},0,150)}}{text}"
                    )

                lines.append(
                    f"Dialogue: 0,{_ass_time(line_start)},{_ass_time(line_end)},Default,,0,0,0,,{text}"
                )
                cue_count += 1

    return header + "\n".join(lines), cue_count, has_estimated
