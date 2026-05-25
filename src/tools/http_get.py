from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx

from .base import ToolResult

_ALLOWED_SCHEMES = {"http", "https"}
_MAX_RESPONSE_LENGTH = 8000

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

_JS_SPA_PATTERNS = re.compile(
    r'<(div|section)\s[^>]*id=["\'](?:app|root|__next|__nuxt)["\']',
    re.IGNORECASE,
)


def _extract_body_text(html: str) -> str:
    """Strip HTML tags and return plain text, focusing on body content."""
    # Try to isolate body content
    body_match = re.search(r"<body[^>]*>(.*?)</body>", html, re.DOTALL | re.IGNORECASE)
    text = body_match.group(1) if body_match else html
    # Remove script/style blocks
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s{2,}", "\n", text).strip()
    return text


def http_get(url: str) -> ToolResult:
    """Fetch a URL and return its text content (truncated to 8000 chars).

    Only allows http:// and https:// schemes to prevent SSRF.
    Sends a browser User-Agent to avoid 403s from sites that block bots.
    Detects JavaScript SPAs and warns the agent to rely on web_search instead.
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
        response = httpx.get(url, timeout=10, follow_redirects=True, headers=_HEADERS)
        response.raise_for_status()

        raw_html = response.text
        content_type = response.headers.get("content-type", "")

        # For HTML responses: strip tags and detect JS SPAs
        if "text/html" in content_type or raw_html.lstrip().startswith("<!"):
            if _JS_SPA_PATTERNS.search(raw_html[:5000]):
                return ToolResult(
                    success=False,
                    output="",
                    error=(
                        "This page is a JavaScript SPA — the HTML contains no readable content. "
                        "Use web_search instead to find information from this site, or try a "
                        "different URL (e.g., a Wikipedia article or a text-based sports results page)."
                    ),
                )
            text = _extract_body_text(raw_html)
        else:
            text = raw_html

        text = text[:_MAX_RESPONSE_LENGTH]
        if len(raw_html) > _MAX_RESPONSE_LENGTH:
            text += f"\n\n[Truncated — {len(raw_html)} total chars]"

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
