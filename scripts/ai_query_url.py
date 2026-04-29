# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click>=8.3.3",
#     "httpx>=0.28.1",
#     "markdownify>=1.2.2",
#     "openai>=2.33.0",
#     "rich>=15.0.0",
# ]
# ///

"""Fetch-and-extract: fetch a web page, convert to markdown, extract via LLM."""

from __future__ import annotations

import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import NamedTuple
from urllib.parse import urlparse

import click
import httpx
import markdownify
from openai import OpenAI
from rich.console import Console

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_URL_LENGTH = 2_000
MAX_CONTENT_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_CHARS_FOR_MODEL = 100_000
FETCH_TIMEOUT_S = 60
MAX_REDIRECTS = 10
CACHE_TTL_S = 15 * 60  # 15 minutes

SECONDARY_MODEL = "gpt-4.1-mini"

console = Console(stderr=True)

# ---------------------------------------------------------------------------
# Redirect policy
# ---------------------------------------------------------------------------

_WWW_RE = re.compile(r"^www\.")


def _is_permitted_redirect(original: str, redirect: str) -> bool:
    orig = urlparse(original)
    redir = urlparse(redirect)

    if redir.scheme != orig.scheme:
        return False
    if (redir.port or 443) != (orig.port or 443):
        return False
    if redir.username or redir.password:
        return False

    strip = lambda h: _WWW_RE.sub("", h or "")  # noqa: E731
    return strip(orig.hostname) == strip(redir.hostname)


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


class CacheEntry(NamedTuple):
    markdown: str
    content_type: str
    status_code: int
    timestamp: float


@dataclass
class URLCache:
    _store: dict[str, CacheEntry] = field(default_factory=dict)
    ttl: float = CACHE_TTL_S

    def get(self, url: str) -> CacheEntry | None:
        entry = self._store.get(url)
        if entry is None:
            return None
        if time.monotonic() - entry.timestamp > self.ttl:
            del self._store[url]
            return None
        return entry

    def put(self, url: str, entry: CacheEntry) -> None:
        self._store[url] = entry


_cache = URLCache()

# ---------------------------------------------------------------------------
# HTTP fetch
# ---------------------------------------------------------------------------


def _fetch(url: str) -> tuple[bytes, str, int]:
    """Fetch *url*, following same-host redirects. Returns (body, content_type, status)."""
    current_url = url
    seen: set[str] = set()

    with httpx.Client(
        follow_redirects=False,
        timeout=FETCH_TIMEOUT_S,
        limits=httpx.Limits(max_connections=5),
    ) as client:
        for _ in range(MAX_REDIRECTS):
            if current_url in seen:
                raise RuntimeError("Redirect loop detected")
            seen.add(current_url)

            resp = client.get(
                current_url,
                headers={
                    "Accept": "text/markdown, text/html, */*",
                    "User-Agent": "fetch-extract/1.0",
                },
            )

            if resp.is_redirect:
                location = resp.headers.get("location", "")
                if not location:
                    raise RuntimeError("Redirect with no Location header")
                # Resolve relative redirects
                location = str(resp.url.join(location))
                if not _is_permitted_redirect(url, location):
                    raise RuntimeError(
                        f"Cross-host redirect blocked: {current_url} → {location}"
                    )
                current_url = location
                continue

            resp.raise_for_status()

            body = resp.content
            if len(body) > MAX_CONTENT_BYTES:
                raise RuntimeError(
                    f"Response body exceeds {MAX_CONTENT_BYTES // (1024 * 1024)} MB"
                )

            content_type = resp.headers.get("content-type", "")
            return body, content_type, resp.status_code

    raise RuntimeError(f"Too many redirects (>{MAX_REDIRECTS})")


# ---------------------------------------------------------------------------
# Content conversion
# ---------------------------------------------------------------------------


def _to_markdown(body: bytes, content_type: str) -> str:
    text = body.decode("utf-8", errors="replace")

    if "text/html" in content_type:
        return markdownify.markdownify(text, strip=["img", "script", "style"])

    # JSON, plain text, XML, markdown — use as-is
    return text


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------


def _truncate(md: str) -> str:
    if len(md) > MAX_CHARS_FOR_MODEL:
        return md[:MAX_CHARS_FOR_MODEL] + "\n\n[Content truncated due to length...]"
    return md


# ---------------------------------------------------------------------------
# Secondary model call
# ---------------------------------------------------------------------------


def _build_prompt(markdown: str, prompt: str) -> str:
    guidelines = (
        "Provide a concise response based on the content above. "
        "Include relevant details, code examples, and documentation excerpts as needed."
    )
    return f"Web page content:\n---\n{markdown}\n---\n\n{prompt}\n\n{guidelines}"


def _make_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        console.print(
            "[bold red]Error:[/bold red] OPENAI_API_KEY environment variable not set."
        )
        sys.exit(1)
    base_url = os.environ.get("OPENAI_BASE_URL")
    return OpenAI(api_key=api_key, base_url=base_url)


def _extract(markdown: str, prompt: str, *, model: str) -> str:
    client = _make_client()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": _build_prompt(markdown, prompt)}],
    )
    choice = resp.choices[0]
    return (choice.message.content or "").strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_and_extract(url: str, prompt: str, *, model: str = SECONDARY_MODEL) -> str:
    cached = _cache.get(url)
    if cached is not None:
        console.print("[dim]cache hit[/dim]")
        markdown = cached.markdown
        content_type = cached.content_type
    else:
        console.print(f"[dim]fetching {url}[/dim]")
        body, content_type, status_code = _fetch(url)

        markdown = _to_markdown(body, content_type)

        _cache.put(
            url,
            CacheEntry(
                markdown=markdown,
                content_type=content_type,
                status_code=status_code,
                timestamp=time.monotonic(),
            ),
        )

    # Shortcut: if already markdown and under limit, return directly
    if "text/markdown" in content_type and len(markdown) <= MAX_CHARS_FOR_MODEL:
        return markdown

    truncated = _truncate(markdown)

    return _extract(truncated, prompt, model=model)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command()
@click.argument("url")
@click.argument("prompt")
@click.option(
    "--model",
    default=SECONDARY_MODEL,
    show_default=True,
    help="Model to use for extraction.",
)
def main(url: str, prompt: str, model: str) -> None:
    """Fetch a web page and extract information using an LLM.

    \b
    Examples:
        python fetch_extract.py https://docs.python.org/3/library/asyncio.html "What is asyncio.run?"
        python fetch_extract.py https://example.com "Summarise this page"
    """
    try:
        result = fetch_and_extract(url, prompt, model=model)
    except (ValueError, RuntimeError, httpx.HTTPError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)

    console.print()
    click.echo(result)


if __name__ == "__main__":
    main()
