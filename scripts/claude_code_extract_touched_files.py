#!/lxhome/lianjie/.local/bin/uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["click>=8.1.8"]
# ///
"""
Extract file paths from Claude Code conversation JSONL logs.

Finds all Write/Edit operations and mv commands, outputs the file paths to stdout.
"""

import json
import shlex
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import click


def extract_mv_destination(command: str) -> str | None:
    """Extract destination path from an mv command (best-effort)."""
    try:
        parts = shlex.split(command)
    except ValueError:
        return None

    if not parts or parts[0] != "mv":
        return None

    # Skip options (args starting with -)
    args = [p for p in parts[1:] if not p.startswith("-")]

    # Simple case: mv src dest
    if len(args) == 2:
        return args[1]

    return None


def extract_file_path_from_line(line: str) -> str | None:
    """
    Extract file path from a JSONL line if it represents a write/create operation.

    Returns the file path or None if not applicable.
    """
    if not line.strip():
        return None

    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None

    if data.get("type") != "assistant":
        return None

    # Check assistant message with Write/Edit tool use
    message = data.get("message", {})
    content = message.get("content", [])
    if not isinstance(content, list):
        return None
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "tool_use":
            continue
        tool_name = item.get("name")
        input_data = item.get("input", {})
        if tool_name in ("Write", "Edit"):
            file_path = input_data.get("file_path")
            if file_path:
                return file_path
        elif tool_name == "Bash":
            command = input_data.get("command", "")
            dest = extract_mv_destination(command)
            if dest:
                return dest

    return None


def extract_paths(file_path: Path) -> set[str]:
    """Extract file paths from a JSONL log file."""
    paths: set[str] = set()
    with open(file_path, encoding="utf-8") as f:
        for line in f:
            path = extract_file_path_from_line(line)
            if path:
                paths.add(path)
    return paths


def filter_existing_paths(paths: set[str], workers: int) -> set[str]:
    """Filter paths to only those that exist on disk, using parallel validation."""
    if not paths:
        return set()

    def check_exists(path: str) -> str | None:
        return path if Path(path).exists() else None

    existing: set[str] = set()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(check_exists, p): p for p in paths}
        for future in as_completed(futures):
            result = future.result()
            if result:
                existing.add(result)

    return existing


@click.command()
@click.argument(
    "jsonl_file", type=click.Path(exists=True, path_type=Path), required=False
)
@click.option(
    "-w",
    "--workers",
    default=4,
    type=int,
    help="Number of parallel workers (default: 4)",
)
def main(jsonl_file: Path | None, workers: int) -> None:
    """Extract written/edited file paths from a Claude Code JSONL log.

    JSONL_FILE can be provided as argument or piped via stdin.
    """
    if jsonl_file is None:
        # Read path from stdin
        jsonl_file = Path(sys.stdin.read().strip())
        if not jsonl_file.exists():
            click.echo(f"Error: {jsonl_file} does not exist", err=True)
            sys.exit(1)

    if not jsonl_file.suffix == ".jsonl":
        click.echo(f"Warning: {jsonl_file} does not have .jsonl extension", err=True)

    try:
        paths = extract_paths(jsonl_file)
    except Exception as e:
        click.echo(f"Error processing file: {e}", err=True)
        sys.exit(1)

    if not paths:
        click.echo("No write/edit operations found.", err=True)
        sys.exit(0)

    paths = filter_existing_paths(paths, workers)
    if not paths:
        click.echo("No written files still exist.", err=True)
        sys.exit(0)

    for path in sorted(paths):
        click.echo(path)


if __name__ == "__main__":
    main()
