import calendar
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx


def normalize_base_url(url: str) -> str:
    """Accept `http://host:20128` or `http://host:20128/v1`; return a base ending in `/v1`."""
    cleaned = url.strip().rstrip("/")
    if not cleaned:
        raise ValueError("Base URL kosong")
    if not urlparse(cleaned).scheme in {"http", "https"}:
        raise ValueError("Base URL harus pakai http:// atau https://")
    if not urlparse(cleaned).path.rstrip("/").endswith("/v1"):
        cleaned += "/v1"
    return cleaned


def _auth_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def test_ai_connection(base_url: str, api_key: str, timeout: float = 10.0) -> dict[str, Any]:
    """GET `{base}/models` with the key. Returns models list, latency, or error."""
    try:
        url = normalize_base_url(base_url) + "/models"
        headers = _auth_headers(api_key)
        started = time.monotonic()
        response = httpx.get(url, headers=headers, timeout=timeout)
        latency_ms = round((time.monotonic() - started) * 1000)
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "models": []}
    except httpx.RequestError as exc:
        return {
            "ok": False,
            "error": f"Tidak bisa menjangkau {base_url}: {exc.__class__.__name__}",
            "models": [],
        }

    if response.status_code != 200:
        detail = ""
        try:
            body = response.json()
            detail = body.get("error", {}).get("message") or body.get("detail") or ""
        except Exception:
            detail = response.text[:200]
        return {
            "ok": False,
            "status_code": response.status_code,
            "error": detail or f"HTTP {response.status_code}",
            "models": [],
        }

    try:
        body = response.json()
        models = [m.get("id") for m in body.get("data", []) if m.get("id")]
    except Exception:
        return {"ok": False, "error": "Respons bukan JSON yang diharapkan", "models": []}

    return {"ok": True, "latency_ms": latency_ms, "models": models[:50]}


def test_ai_chat(
    base_url: str, api_key: str, model: str, timeout: float = 30.0
) -> dict[str, Any]:
    """POST a tiny completion to `/chat/completions`.

    `test_ai_connection` only reads `/models`, which can succeed while the chat
    path (the one analysis uses) is slow, blocked, or misconfigured. This makes
    that difference visible before the user starts a real analysis job.
    """
    try:
        base = normalize_base_url(base_url)
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "model": model}

    if not model:
        return {
            "ok": False,
            "error": "Model kosong — isi nama model persis seperti di 9Router.",
            "model": model,
        }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Balas satu kata: ok"}],
        "max_tokens": 8,
        "temperature": 0,
    }
    headers = {**_auth_headers(api_key), "Content-Type": "application/json"}
    started = time.monotonic()

    try:
        response = httpx.post(
            f"{base}/chat/completions", headers=headers, json=payload, timeout=timeout
        )
    except httpx.TimeoutException as exc:
        return {
            "ok": False,
            "model": model,
            "error": (
                f"Timeout {timeout:.0f}s ({type(exc).__name__}) — model lambat atau "
                "9Router tidak membalas."
            ),
        }
    except httpx.RequestError as exc:
        return {
            "ok": False,
            "model": model,
            "error": f"Tidak bisa menjangkau chat endpoint ({type(exc).__name__}): {str(exc) or 'tanpa detail'}",
        }

    latency_ms = round((time.monotonic() - started) * 1000)

    if response.status_code != 200:
        detail = ""
        try:
            body = response.json()
            detail = body.get("error", {}).get("message") or body.get("detail") or ""
        except Exception:
            detail = response.text[:300]
        return {
            "ok": False,
            "model": model,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "error": detail or f"HTTP {response.status_code}",
        }

    try:
        body = response.json()
        reply = body["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        return {
            "ok": False,
            "model": model,
            "latency_ms": latency_ms,
            "error": "Respons bukan format chat completion",
        }

    return {
        "ok": True,
        "model": model,
        "latency_ms": latency_ms,
        "reply": str(reply).strip()[:200],
    }


def _next_cycle_reset() -> str:
    """OpenAI-style billing resets on the 1st of the next month (UTC)."""
    now = datetime.now(timezone.utc)
    if now.month == 12:
        year, month = now.year + 1, 1
    else:
        year, month = now.year, now.month + 1
    return datetime(year, month, 1, 0, 0, tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _monthly_range() -> tuple[str, str]:
    """OpenAI billing wants month start/end dates like 2026-11-01 → 2026-11-30."""
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, 1)
    last_day = calendar.monthrange(now.year, now.month)[1]
    end = datetime(now.year, now.month, last_day)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _fetch_json(url: str, headers: dict[str, str], timeout: float) -> dict[str, Any] | None:
    try:
        response = httpx.get(url, headers=headers, timeout=timeout)
    except httpx.RequestError:
        return None
    if response.status_code != 200:
        return None
    try:
        return response.json()
    except Exception:
        return None


def fetch_ai_quota(base_url: str, api_key: str, timeout: float = 10.0) -> dict[str, Any]:
    """Try OpenAI-compatible billing endpoints. Missing/401 → available: false."""
    try:
        base = normalize_base_url(base_url)
    except ValueError as exc:
        return {"available": False, "error": str(exc)}

    headers = _auth_headers(api_key)
    subscription = _fetch_json(f"{base}/dashboard/billing/subscription", headers, timeout)
    usage_start, usage_end = _monthly_range()
    usage_url = f"{base}/dashboard/billing/usage?start_date={usage_start}&end_date={usage_end}"
    usage = _fetch_json(usage_url, headers, timeout)

    if subscription is None and usage is None:
        return {
            "available": False,
            "error": "Provider tidak mengekspos OpenAI billing endpoints di URL ini.",
        }

    total = None
    used = None
    reset_at = None
    plan = None

    if subscription:
        total = (
            subscription.get("hard_limit_usd")
            or subscription.get("total_granted")
            or subscription.get("soft_limit_usd")
        )
        reset_at_raw = subscription.get("access_until")
        if isinstance(reset_at_raw, (int, float)) and reset_at_raw > 0:
            reset_at = datetime.fromtimestamp(reset_at_raw, tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        plan = subscription.get("plan", {}).get("title") if isinstance(subscription.get("plan"), dict) else None

    if usage:
        cents = usage.get("total_usage")
        if isinstance(cents, (int, float)):
            used = cents / 100.0

    if total is None and used is None:
        return {"available": False, "error": "Endpoint billing ada, tapi field kuota tidak dikenali."}

    remaining = None
    if total is not None and used is not None:
        remaining = max(total - used, 0)
    if not reset_at:
        reset_at = _next_cycle_reset()

    return {
        "available": True,
        "total": total,
        "used": used,
        "remaining": remaining,
        "reset_at": reset_at,
        "plan": plan,
    }
