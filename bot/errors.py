from __future__ import annotations

import httpx

from config import settings

_GENERIC_ERROR = "server error"
_MAX_ERROR_LEN = 500


def user_facing_error(exc: Exception) -> str:
    if not settings.show_detailed_errors:
        return _GENERIC_ERROR
    text = _format_exception(exc)
    if len(text) > _MAX_ERROR_LEN:
        return text[: _MAX_ERROR_LEN - 1] + "…"
    return text


def _format_exception(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        body = exc.response.text.strip()
        if body:
            body = body[:200]
            return f"HTTP {exc.response.status_code} {exc.request.url}: {body}"
        return f"HTTP {exc.response.status_code} {exc.request.url}"
    if isinstance(exc, httpx.TimeoutException):
        url = exc.request.url if exc.request else "unknown"
        return f"Timeout: {url}"
    if isinstance(exc, httpx.ConnectError):
        return f"Connect error: {exc}"
    if isinstance(exc, httpx.RequestError):
        return f"Request error: {exc}"
    return f"{type(exc).__name__}: {exc}"
