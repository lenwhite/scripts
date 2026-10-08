# /// script
# requires-python = ">=3.12"
# dependencies = ["click>=8.1.8"]
# ///
"""
Multi-language autoformat script.

Formats and checks files based on their type, running commands in order
from cheapest to most expensive, failing early if any command fails.

Positioning
-----------
This is a personal, local CLI tool - think `ripgrep`, not a repo-committed
formatter. It is intentionally NOT coupled to any specific repo's tooling
config (no parsing of `pyproject.toml` for tool settings, no respect for
project-level formatter settings beyond detection-based opt-in).
Requirements here are shaped by personal/agentic workflows, which differ
from repo-level CI configurations.

Project-specific behavior is handled via in-script prereq detection
(e.g., mypy only runs when a project's `pyproject.toml` mentions it, and
JS tools only run when the project has them installed), not by honoring
project config files.
"""

import os
import subprocess
import sys
from collections import defaultdict
from functools import cache
from pathlib import Path
from typing import NotRequired, TypedDict

import click


class Prereq(TypedDict):
    cmd: list[str]
    invert: NotRequired[bool]


class CommandConfig(TypedDict):
    cmd: list[str]
    append_files: bool
    prereqs: NotRequired[list[Prereq]]


class FileTypeConfig(TypedDict):
    extensions: list[str]
    commands: list[CommandConfig]


# Runners that only resolve binaries the project already has installed, so a
# missing tool fails its prereq instead of being fetched from the registry.
JS_RUNNERS: dict[str, list[str]] = {
    "bun.lockb": ["bunx", "--no-install"],
    "bun.lock": ["bunx", "--no-install"],
    "yarn.lock": ["yarn", "run", "-T", "-B"],
    "pnpm-lock.yaml": ["pnpm", "exec"],
    "package-lock.json": ["npx", "--no-install"],
}


def detect_js_runner() -> list[str]:
    """Pick the JS binary runner from the nearest lockfile at or above the cwd."""
    cwd = Path.cwd()
    for directory in [cwd, *cwd.parents]:
        for lockfile, runner in JS_RUNNERS.items():
            if (directory / lockfile).exists():
                return runner
    return ["npx", "--no-install"]


JS_RUNNER = detect_js_runner()


def js_bin_installed(name: str, *, invert: bool = False) -> Prereq:
    """Prereq that passes when the project has the `name` binary installed."""
    return {"cmd": [*JS_RUNNER, name, "--version"], "invert": invert}


# File type definitions with commands ordered cheapest → most expensive.
# Commands can have "prereqs": a command is skipped unless every prereq command
# exits 0 (or non-zero, for prereqs with "invert").
#
# TODO: per the positioning in the module docstring, FILE_TYPES is currently
# embedded as the single source of config. It may move to an external local
# config (e.g., ~/.config/autofmt/config.toml) with optional per-project
# overrides (e.g., .autofmt.toml in a repo root). Not committed to a specific
# design yet - this note exists to flag the intent.
FILE_TYPES: dict[str, FileTypeConfig] = {
    "python": {
        "extensions": [".py"],
        "commands": [
            {
                "cmd": ["uv", "run", "--with", "ruff", "ruff", "format"],
                "append_files": True,
            },
            {
                "cmd": ["uv", "run", "--with", "ruff", "ruff", "check"],
                "append_files": True,
            },
            {
                "cmd": ["uv", "run", "ty", "check"],
                "append_files": True,
                "prereqs": [{"cmd": ["rg", "-qw", "ty", "pyproject.toml"]}],
            },
            {
                "cmd": ["uv", "run", "mypy"],
                "append_files": True,
                "prereqs": [{"cmd": ["rg", "-q", "mypy", "pyproject.toml"]}],
            },
            {
                "cmd": ["uv", "run", "pyright"],
                "append_files": True,
                "prereqs": [{"cmd": ["rg", "-q", "pyright", "pyproject.toml"]}],
            },
        ],
    },
    "typescript or javascript": {
        "extensions": [".js", ".ts", ".jsx", ".tsx"],
        "commands": [
            {
                "cmd": [*JS_RUNNER, "biome", "check", "--write", "--error-on-warnings"],
                "append_files": True,
                "prereqs": [js_bin_installed("biome")],
            },
            {
                "cmd": [*JS_RUNNER, "prettier", "--write"],
                "append_files": True,
                "prereqs": [
                    js_bin_installed("biome", invert=True),
                    js_bin_installed("prettier"),
                ],
            },
            {
                "cmd": [*JS_RUNNER, "tsc", "--noEmit"],
                "append_files": False,
                "prereqs": [
                    {"cmd": ["test", "-f", "tsconfig.json"]},
                    js_bin_installed("tsc"),
                ],
            },
            {
                "cmd": [
                    *JS_RUNNER,
                    "eslint",
                    "--max-warnings",
                    "0",
                    "--no-warn-ignored",
                ],
                "append_files": True,
                "prereqs": [
                    js_bin_installed("biome", invert=True),
                    js_bin_installed("eslint"),
                ],
            },
        ],
    },
}


def get_file_type(path: Path) -> str | None:
    suffix = path.suffix.lower()
    for type_key, config in FILE_TYPES.items():
        if suffix in config["extensions"]:
            return type_key
    return None


def group_files_by_type(files: list[Path]) -> dict[str, list[Path]]:
    grouped: dict[str, list[Path]] = defaultdict(list)
    for file in files:
        file_type = get_file_type(file)
        if file_type:
            grouped[file_type].append(file)
    return grouped


MAX_OUTPUT_CHARS = 2500
MAX_OUTPUT_LINES = 100


def truncate_output(output: str) -> str:
    """Truncate output to MAX_OUTPUT_CHARS or MAX_OUTPUT_LINES, whichever is smaller."""
    lines = output.splitlines(keepends=True)
    if len(lines) > MAX_OUTPUT_LINES:
        output = (
            "".join(lines[:MAX_OUTPUT_LINES])
            + f"\n... truncated ({MAX_OUTPUT_LINES} lines shown)\n"
        )
    if len(output) > MAX_OUTPUT_CHARS:
        output = (
            output[:MAX_OUTPUT_CHARS]
            + f"\n... truncated ({MAX_OUTPUT_CHARS} chars shown)\n"
        )
    return output


env = os.environ.copy()
env.pop("VIRTUAL_ENV", None)


@cache
def prereq_cmd_succeeds(cmd: tuple[str, ...]) -> bool:
    """Run a prerequisite command once. A missing executable counts as failure."""
    try:
        result = subprocess.run(cmd, capture_output=True, env=env, check=False)
    except FileNotFoundError:
        return False
    return result.returncode == 0


def check_prereqs(prereqs: list[Prereq]) -> bool:
    """Return True if every prereq passes (exit 0, or non-zero when inverted)."""
    return all(
        prereq_cmd_succeeds(tuple(prereq["cmd"])) != prereq.get("invert", False)
        for prereq in prereqs
    )


@click.command()
@click.argument("files", nargs=-1, type=click.Path(exists=True, path_type=Path))
def main(files: tuple[Path, ...]) -> None:
    """Format and check files based on their type.

    FILES can be provided as arguments or piped via stdin (one path per line).
    """
    paths = list(files)
    if not paths:
        paths = [
            Path(stripped)
            for line in sys.stdin.read().splitlines()
            if (stripped := line.strip())
        ]
        for p in paths:
            if not p.exists():
                raise click.BadParameter(
                    f"Path '{p}' does not exist.", param_hint="files"
                )
    if not paths:
        return

    grouped = group_files_by_type(paths)

    if not grouped:
        click.echo("No supported files found.")
        return

    for file_type, type_files in grouped.items():
        click.echo(
            f"Processing {file_type} files: {', '.join(str(f) for f in type_files)}"
        )

        for cmd_config in FILE_TYPES[file_type]["commands"]:
            if not check_prereqs(cmd_config.get("prereqs", [])):
                continue

            cmd = cmd_config["cmd"]
            result = subprocess.run(
                [*cmd, *type_files] if cmd_config["append_files"] else cmd,
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            if result.returncode != 0:
                # e.g., "yarn run -T -B prettier --write"
                click.echo(f"Error: {' '.join(cmd)} failed", err=True)
                click.echo(truncate_output(result.stdout + result.stderr), err=True)
                sys.exit(2)

    click.echo(f"Done. Processed: {', '.join(grouped)}")


if __name__ == "__main__":
    main()
