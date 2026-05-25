from __future__ import annotations

from urllib.parse import urlparse

import httpx

from .base import ToolResult

_ALLOWED_SCHEMES = {"http", "https"}
_MAX_RESPONSE_LENGTH = 4000


def http_get(url: str) -> ToolResult:
    """Fetch a URL and return its text content (truncated to 4000 chars).

    Only allows http:// and https:// schemes to prevent SSRF.
    """
    # Validate URL scheme
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        return ToolResult(
            success=False,
            output="",
            error=f"Invalid URL scheme '{parsed.scheme}'. Only http and https are allowed.",
        )

    if not parsed.netloc:
        return ToolResult(success=False, output="", error="Invalid URL: no host specified.")

    try:
        response = httpx.get(url, timeout=10, follow_redirects=True)
        response.raise_for_status()

        text = response.text[:_MAX_RESPONSE_LENGTH]
        if len(response.text) > _MAX_RESPONSE_LENGTH:
            text += f"\n\n[Truncated — {len(response.text)} total chars]"

        return ToolResult(success=True, output=text)

    except httpx.TimeoutException:
        raise  # Let retry decorator handle
    except httpx.ConnectError:
        raise  # Let retry decorator handle
    except httpx.HTTPStatusError as e:
        return ToolResult(
            success=False, output="", error=f"HTTP {e.response.status_code}: {e.response.reason_phrase}"
        )
    except Exception as e:
        return ToolResult(success=False, output="", error=f"Request failed: {e}")
