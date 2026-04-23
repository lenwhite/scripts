# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click>=8.1.8",
# ]
#
# ///

import json
import shutil
from pathlib import Path
import re
import sys
import click


def get_settings_path(local: bool) -> Path:
    if local:
        return Path(".claude/settings.local.json")
    return Path.home() / ".claude" / "settings.json"


def load_settings(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {}


def save_settings(path: Path, settings: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n")


def delete_hooks(hooks: list, pattern: str) -> None:
    hooks[:] = [h for h in hooks if f"check '{pattern}'" not in h.get("command", "")]


@click.group()
def cli():
    """Claude Code config shortcut."""
    pass


@cli.command()
@click.argument("pattern")
@click.argument("reason")
def check(pattern: str, reason: str):
    """Check stdin JSON against pattern. Used by PreToolUse hooks."""

    data = sys.stdin.read()
    try:
        obj = json.loads(data)
        command = obj.get("tool_input", {}).get("command", "")
    except json.JSONDecodeError as e:
        print(f"Error: {e}", file=sys.stdout)
        print(data, file=sys.stdout)
        sys.exit(1)

    regex = pattern.replace(":*", ".*")
    if re.match(f"^{regex}", command):
        print(reason, file=sys.stderr)
        print(reason)
        sys.exit(2)
    sys.exit(0)


@cli.command()
@click.option("--local", is_flag=True, help="Modify ./.claude/settings.local.json")
@click.argument("pattern")
def allow(local: bool, pattern: str):
    """Add a pattern to permissions.allow."""
    path = get_settings_path(local)

    if not path.exists():
        if not click.confirm(f"{path} does not exist. Create it?"):
            raise SystemExit(1)
        settings = {}
    else:
        settings = load_settings(path)

    permissions = settings.setdefault("permissions", {})
    allow_list = permissions.setdefault("allow", [])

    if not pattern.endswith(":*"):
        pattern = f"{pattern}:*"

    entry = f"Bash({pattern})"
    if entry in allow_list:
        click.echo(f"Already allowed: {entry}")
        return

    allow_list.append(entry)
    save_settings(path, settings)
    click.echo(f"Added to {path}: {entry}")


@cli.command()
@click.option("--local", is_flag=True, help="Modify ./.claude/settings.local.json")
@click.argument("pattern")
@click.argument("reason", required=False)
def deny(local: bool, pattern: str, reason: str | None):
    """Add a pattern to permissions.deny, or as a hook with a reason."""
    path = get_settings_path(local)

    if not path.exists():
        if not click.confirm(f"{path} does not exist. Create it?"):
            raise SystemExit(1)
        settings = {}
    else:
        settings = load_settings(path)

    if not pattern.endswith(":*"):
        pattern = f"{pattern}:*"

    permissions = settings.setdefault("permissions", {})
    deny_list = permissions.setdefault("deny", [])

    entry = f"Bash({pattern})"
    if entry not in deny_list:
        deny_list.append(entry)
        click.echo(f"Added to {path}: {entry}")
    else:
        click.echo(f"Already denied: {entry}")

    if reason is not None:
        # Also add as PreToolUse hook with reason
        hooks = settings.setdefault("hooks", {})
        pre_tool_use = hooks.setdefault("PreToolUse", [])

        uv_path = shutil.which("uv") or "uv"
        script_path = Path(__file__).resolve()
        command = f"{uv_path} run {script_path} check '{pattern}' '{reason.replace("'", "'\\''")}'"
        hook = {"type": "command", "command": command}

        existing = next((e for e in pre_tool_use if e.get("matcher") == "Bash"), None)
        if existing:
            delete_hooks(existing["hooks"], pattern)
            existing["hooks"].append(hook)
        else:
            pre_tool_use.append({"matcher": "Bash", "hooks": [hook]})

        click.echo(
            f"  Reason: {reason} (deny reason will be shown only when claude restarts)"
        )

    save_settings(path, settings)


if __name__ == "__main__":
    cli()
