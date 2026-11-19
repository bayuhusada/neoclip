import json
import re
from typing import Any

from app.core.config import settings
from app.services.ai import normalize_base_url
from app.services.ai_config import get_effective_config

# Keep requests small enough that a local/free model can finish inside the
# timeout. Both are safety caps, not quality targets.
MAX_TRANSCRIPT_CHARS = 8000
MAX_OUTPUT_TOKENS = 1200

# System prompt for clip extraction. Keep it strict JSON so we can parse reliably.
SYSTEM_PROMPT = """Anda adalah editor video yang mengekstrak klip menarik dari transkrip panjang.
Tugas: baca transkrip (dengan timestamp), pilih 3-6 klip terbaik untuk konten vertikal 9:16 (TikTok/Reels/Shorts).

ATURAN:
1. Setiap klip: 15-60 detik, fokus pada satu topik/hook.
2. Prioritaskan momen: konflik, kejutan (twist), wawasan (insight), emosi (humor/sedih), ajakan aksi.
3. Hindari pengenalan umum, basa-basi, atau bagian lambat.
4. Output HARUS JSON object: {"clips": [ ... ]} dengan tiap item:
   {
     "title": "Judul klip (maks 80 karakter)",
     "hook": "Satu kalimat pembuka yang menarik perhatian (maks 160 karakter)",
     "start_sec": angka detik mulai,
     "end_sec": angka detik selesai,
     "score": 0.0-1.0 (kepentingan),
     "rationale": "Mengapa klip ini layak dipilih (maks 200 karakter)"
   }
5. start_sec < end_sec, durasi 15-60 detik.
6. Urutkan dari skor tertinggi.
7. Jika transkrip pendek/kurang menarik, kembalikan {"clips": []}.

JANGAN tambahkan teks lain di luar JSON.
"""

USER_PROMPT_TEMPLATE = """Transkrip video (durasi total {duration:.1f} detik):
---
{transcript}
---
Ekstrak klip terbaik sesuai aturan di atas."""


def build_analysis_payload(transcript_text: str, duration_sec: float) -> dict[str, Any]:
    return {
        "model": get_effective_config()["model"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT_TEMPLATE.format(
                duration=duration_sec,
                transcript=transcript_text[:MAX_TRANSCRIPT_CHARS],
            )},
        ],
        "temperature": 0.3,
        "max_tokens": MAX_OUTPUT_TOKENS,
        "stream": False,  # prevent SSE/chunked response from 9Router/Gemini
        "response_format": {"type": "json_object"},  # some providers ignore this
    }


def build_timeout() -> "httpx.Timeout":
    """Short connect timeout, long read timeout for slow local models."""
    import httpx

    total = float(settings.ai_timeout_sec)
    return httpx.Timeout(connect=min(10.0, total), read=total, write=30.0, pool=total)


def _extract_content_from_message(message: Any) -> str:
    """Extract content from various possible fields in an AI message.
    
    Order of preference for reasoning models:
    1. message.content
    2. message.reasoning_content (DeepSeek-R1, etc.)
    3. message.reasoning (QwQ, others)
    4. message.tool_calls[].function.arguments (if a tool call was made)
    
    Returns empty string if no content is found.
    """
    if not isinstance(message, dict):
        return ""

    # 1. Try regular content first
    content = message.get("content")
    if content:
        return str(content).strip()

    # 2. Try reasoning_content (DeepSeek-R1, ds thinking, etc.)
    reasoning_content = message.get("reasoning_content")
    if reasoning_content:
        return str(reasoning_content).strip()

    # 3. Try reasoning field (QwQ, some other models)
    reasoning = message.get("reasoning")
    if reasoning:
        return str(reasoning).strip()

    # 4. Try tool_calls for tool-based reasoning
    tool_calls = message.get("tool_calls")
    if tool_calls:
        for tool_call in tool_calls:
            if isinstance(tool_call, dict) and "function" in tool_call:
                args = tool_call["function"].get("arguments")
                if args:
                    return str(args).strip()

    return ""


def parse_ai_response(raw: str) -> list[dict[str, Any]]:
    """Parse AI response into a list of clip dicts. Returns [] when unusable."""
    data: Any = None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", raw, re.DOTALL)
        if not match:
            return []
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return []

    # Accept both a bare array and the documented {"clips": [...]} envelope.
    if isinstance(data, dict):
        data = data.get("clips")
    if not isinstance(data, list):
        return []

    clips = []
    for item in data:
        if not isinstance(item, dict):
            continue

        title = item.get("title")
        start = item.get("start_sec")
        end = item.get("end_sec")
        if not isinstance(title, str) or not title.strip():
            continue
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            continue
        start, end = float(start), float(end)
        if start < 0 or end <= start:
            continue
        if not 5 <= (end - start) <= 120:
            continue

        try:
            score = float(item.get("score") or 0.5)
        except (TypeError, ValueError):
            score = 0.5
        score = min(max(score, 0.0), 1.0)

        clips.append(
            {
                "title": title.strip()[:300],
                "hook": str(item.get("hook") or "").strip()[:2000] or None,
                "start_sec": start,
                "end_sec": end,
                "score": score,
                "rationale": str(item.get("rationale") or "").strip()[:2000] or None,
            }
        )

    clips.sort(key=lambda clip: clip["score"], reverse=True)
    return clips[:8]  # hard cap; more than this is noise for a single video


def _parse_sse_body(raw: str) -> dict[str, Any] | None:
    """Rebuild a normal completion body from an SSE stream.

    Some OpenAI-compatible routers (9Router + Gemini) stream chunks even when
    the request asks for `stream: false`. The chunks carry `delta.content`;
    concatenating them gives the same text a non-streaming reply would have.
    """
    if "data:" not in raw:
        return None

    parts: list[str] = []
    model: str | None = None
    finish_reason: str | None = None

    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            chunk = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if not isinstance(chunk, dict):
            continue

        model = model or chunk.get("model")
        for choice in chunk.get("choices") or []:
            if not isinstance(choice, dict):
                continue
            delta = choice.get("delta") or {}
            if isinstance(delta.get("content"), str):
                parts.append(delta["content"])
            reasoning = delta.get("reasoning_content") or delta.get("reasoning")
            if isinstance(reasoning, str):
                parts.append(reasoning)
            if choice.get("finish_reason"):
                finish_reason = choice["finish_reason"]

    if not parts:
        return None

    return {
        "model": model,
        "choices": [
            {
                "message": {"role": "assistant", "content": "".join(parts)},
                "finish_reason": finish_reason,
            }
        ],
    }


def _load_body(response: Any) -> dict[str, Any]:
    """Return the completion body, tolerating an accidental SSE stream."""
    try:
        body = response.json()
    except ValueError:
        body = _parse_sse_body(getattr(response, "text", ""))
        if body is None:
            raw = getattr(response, "text", "")[:500]
            raise RuntimeError(
                f"AI endpoint returned non-JSON body ({response.status_code}): {raw!r}"
            )
    if not isinstance(body, dict):
        raw = getattr(response, "text", "")[:500]
        raise RuntimeError(
            f"AI endpoint returned unexpected JSON ({response.status_code}): {raw!r}"
        )
    return body


async def analyze_transcript(transcript_text: str, duration_sec: float) -> list[dict[str, Any]]:
    """Call 9Router with the transcript and return parsed clip candidates."""
    cfg = get_effective_config()
    if not cfg.get("api_key") or not cfg.get("model"):
        raise ValueError("AI not configured: missing api_key or model in settings")

    try:
        base = normalize_base_url(cfg["base_url"])
    except ValueError as exc:
        raise ValueError(f"Invalid base URL: {exc}") from exc

    import httpx

    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    payload = build_analysis_payload(transcript_text, duration_sec)
    timeout_sec = float(settings.ai_timeout_sec)
    url = f"{base}/chat/completions"

    try:
        async with httpx.AsyncClient(timeout=build_timeout()) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 400 and "response_format" in payload:
                # Some OpenAI-compatible routers reject `response_format`. The
                # parser already tolerates prose/fenced JSON, so retry once
                # without it instead of failing the whole job.
                retry_payload = {k: v for k, v in payload.items() if k != "response_format"}
                response = await client.post(url, headers=headers, json=retry_payload)
    except httpx.TimeoutException as exc:
        # httpx timeout exceptions stringify to "", so name the class explicitly.
        raise RuntimeError(
            f"Timeout AI setelah {timeout_sec:.0f} detik ({type(exc).__name__}) — model terlalu "
            "lambat atau 9Router tidak membalas. Naikkan AI_TIMEOUT_SEC atau pakai model lebih cepat."
        ) from exc
    except httpx.RequestError as exc:
        reason = str(exc) or "tanpa detail"
        raise RuntimeError(f"Cannot reach AI endpoint ({type(exc).__name__}): {reason}") from exc

    if response.status_code != 200:
        detail = ""
        try:
            body = response.json()
            detail = body.get("error", {}).get("message") or body.get("detail") or ""
        except Exception:
            detail = response.text[:300]
        raise RuntimeError(f"AI API error {response.status_code}: {detail}")

    # Parse response body (tolerates accidental SSE stream)
    body = _load_body(response)

    # Extract finish_reason for retry decisions
    choice = body.get("choices", [{}])[0]
    finish_reason = choice.get("finish_reason")

    # Extract content using helper that tries multiple fields
    message = choice.get("message")
    content = _extract_content_from_message(message)

    # Diagnostic logging
    import logging
    logger = logging.getLogger(__name__)
    logger.debug("AI response: model=%s, finish_reason=%s", body.get("model"), finish_reason)

    # Retry for length error with larger max_tokens
    if finish_reason == "length" and content:
        logger.info("AI response truncated (%s). Retrying with increased max_tokens.", finish_reason)
        retry_payload = {
            **payload,
            "max_tokens": payload.get("max_tokens", MAX_OUTPUT_TOKENS) * 2,
            "response_format": None,  # Some models ignore this anyway
        }
        async with httpx.AsyncClient(timeout=build_timeout()) as client:
            response = await client.post(url, headers=headers, json=retry_payload)
            # Re-parse response (tolerates accidental SSE stream)
            body = _load_body(response)
            choice = body.get("choices", [{}])[0]
            finish_reason = choice.get("finish_reason")
            message = choice.get("message")
            content = _extract_content_from_message(message)
            logger.debug("AI retry: model=%s, finish_reason=%s", body.get("model"), finish_reason)

    # Handle empty content after retries or if not length error
    if not content or not content.strip():
        logger.error(
            "AI returned empty content. model=%s, finish_reason=%s, message_keys=%s",
            body.get("model"),
            finish_reason,
            list(message.keys()) if isinstance(message, dict) else "N/A",
        )
        # Give actionable error hint based on finish reason
        if finish_reason == "length":
            raise RuntimeError(
                f"AI response truncated (length). Try switching to a different model or "
                "increase AI_MAX_OUTPUT_TOKENS in settings."
            )
        if finish_reason == "error":
            raise RuntimeError(
                f"AI model returned an error (finish_reason={finish_reason}). "
                "Check model availability and API key configuration."
            )
        raise RuntimeError(
            f"AI response content is empty (finish_reason={finish_reason}). "
            "Possible reasoning model? Ensure the model supports JSON output. "
            "If using a reasoning model (DeepSeek-R1, QwQ, etc.), switch to a "
            "non‑reasoning model like deepseek‑v3, gemini‑2.5‑flash, or qwen‑2.5."
        )

    try:
        return parse_ai_response(content)
    except Exception as exc:
        # Keep the raw head so a bad/empty model reply is diagnosable.
        logger.error("AI parse failed. Raw content: %r", content[:500])
        raise RuntimeError(f"Failed to parse AI response: {exc}") from exc


# Re-export for tests
__all__ = [
    "analyze_transcript",
    "parse_ai_response",
    "build_analysis_payload",
    "build_timeout",
    "MAX_TRANSCRIPT_CHARS",
    "MAX_OUTPUT_TOKENS",
    "SYSTEM_PROMPT",
]