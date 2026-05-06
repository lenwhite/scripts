#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click>=8.3.3",
#     "openai>=2.33.0",
#     "rich>=15.0.0",
# ]
# ///

"""Read text from stdin and query an LLM about it."""

from __future__ import annotations

import os
import sys

import click
from openai import OpenAI
from rich.console import Console

MAX_CHARS_FOR_MODEL = 100_000
DEFAULT_MODEL = "gpt-4.1-mini"

console = Console(stderr=True)


def _truncate(text: str) -> str:
    if len(text) > MAX_CHARS_FOR_MODEL:
        return text[:MAX_CHARS_FOR_MODEL] + "\n\n[Content truncated due to length...]"
    return text


def _build_prompt(content: str, prompt: str) -> str:
    guidelines = (
        "Provide a concise response based on the content above. "
        "Include relevant details, code examples, and documentation excerpts as needed."
    )
    return f"Content:\n---\n{content}\n---\n\n{prompt}\n\n{guidelines}"


def _make_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        console.print(
            "[bold red]Error:[/bold red] OPENAI_API_KEY environment variable not set."
        )
        sys.exit(1)
    base_url = os.environ.get("OPENAI_BASE_URL")
    return OpenAI(api_key=api_key, base_url=base_url)


def _query(content: str, prompt: str, *, model: str) -> str:
    client = _make_client()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": _build_prompt(content, prompt)}],
    )
    choice = resp.choices[0]
    return (choice.message.content or "").strip()


@click.command()
@click.argument("prompt")
@click.option(
    "--model",
    default=DEFAULT_MODEL,
    show_default=True,
    help="Model to use for the query.",
)
def main(prompt: str, model: str) -> None:
    """Read text from stdin and query an LLM about it.

    \b
    Examples:
        cat README.md | ask_llm.py "Summarise this"
        git diff | ask_llm.py "Review these changes"
        fetch_url.py https://example.com | ask_llm.py "What is this about?"
    """
    if sys.stdin.isatty():
        console.print("[yellow]Warning:[/yellow] Reading from stdin (Ctrl+D to end)")

    content = sys.stdin.read()
    if not content.strip():
        console.print("[red]Error:[/red] No input received on stdin.")
        sys.exit(1)

    truncated = _truncate(content)

    try:
        result = _query(truncated, prompt, model=model)
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        sys.exit(1)

    click.echo(result)


if __name__ == "__main__":
    main()
