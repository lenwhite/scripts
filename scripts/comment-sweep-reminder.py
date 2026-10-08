# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
Script to remind the agent to remove comments and docstrings.

Takes the list of modified files as arguments (used for caching the reminder so it only runs once per set of files).

Meant to be used with the `stop-gate.py` script (which triggers this script) and the `claude_code_extract_touched_files.py` script (which provides the list of modified files).
"""
import hashlib
import sys
import tempfile
from pathlib import Path

COMMENT_SWEEP_PROMPT = """\
Auto-format/lint/typecheck passed on the files you just edited.

One more pass before you stop: remove all comments you added during this
implementation, including docstrings. Comments and docstrings should only be
added when the user specifically asked for them.

Exception: comments which are outdated should be minimally edited or removed.

Where needed, change variable names to be more readable and expressive
without comments

Leave directive/pragma comments (e.g. eslint-disable, ts-expect-error,
type: ignore, noqa) alone.
If you added no comments, just say so and stop."""


def marker_path(files: list[str]) -> Path:
    resolved = sorted(str(Path(file).resolve()) for file in files)
    digest = hashlib.sha256("\0".join(resolved).encode()).hexdigest()
    return Path(tempfile.gettempdir()) / "stop-gate" / digest


def main() -> int:
    marker = marker_path(sys.argv[1:])
    if marker.exists():
        marker.unlink()
        return 0

    marker.parent.mkdir(exist_ok=True)
    marker.touch()
    print(COMMENT_SWEEP_PROMPT)
    return 1


if __name__ == "__main__":
    sys.exit(main())
