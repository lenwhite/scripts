#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click>=8.3.3",
#     "httpx>=0.28.1",
#     "markdownify>=1.2.2",
#     "rich>=15.0.0",
# ]
# ///

"""Fetch a web page and convert it to markdown."""

from __future__ import annotations

import re
import sys
from urllib.parse import urlparse

import click
import httpx
import markdownify
from rich.console import Console

MAX_CONTENT_BYTES = 10 * 1024 * 1024  # 10 MB
FETCH_TIMEOUT_S = 60
MAX_REDIRECTS = 10

console = Console(stderr=True)

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


def _to_markdown(body: bytes, content_type: str) -> str:
    text = body.decode("utf-8", errors="replace")

    if "text/html" in content_type:
        return markdownify.markdownify(text, strip=["img", "script", "style"])

    return text


@click.command()
@click.argument("url")
def main(url: str) -> None:
    """Fetch a web page and output it as markdown.

    \b
    Examples:
        fetch_url.py https://docs.python.org/3/library/asyncio.html
        fetch_url.py https://example.com | ask_llm.py "Summarise this page"
    """
    try:
        console.print(f"[dim]fetching {url}[/dim]")
        body, content_type, _status = _fetch(url)
        markdown = _to_markdown(body, content_type)
    except (RuntimeError, httpx.HTTPError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)

    click.echo(markdown)


if __name__ == "__main__":
    main()
