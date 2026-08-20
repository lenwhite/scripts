#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "click",
#   "openai",
#   "pydantic",
#   "rich",
# ]
# ///

import os
import subprocess
import sys

import click
from openai import OpenAI, OpenAIError
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel

console = Console()


class CommitMessage(BaseModel):
    not_enough_context: bool = Field(
        description="Set to true if the intent of the changes is ambiguous, or otherwise unclear from the diff."
        "If the intent is clear, set to false and write a commit message.",
    )
    message: str = Field(
        description="The conventional-commit message. "
        "Leave empty when not_enough_context is true.",
    )


def try_subprocess_run(args, *, error_msg, exit_on_error=True):
    try:
        result = subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]{error_msg}:[/bold red] {e.stderr}")
        if exit_on_error:
            sys.exit(1)
        return None
    except (UnicodeDecodeError, UnicodeError) as e:
        console.print(f"[bold red]Unicode error {error_msg.lower()}:[/bold red] {e}")
        if exit_on_error:
            sys.exit(1)
        return None


def is_git_repository():
    result = try_subprocess_run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        error_msg="Error checking git repository",
        exit_on_error=False,
    )
    return result is not None


def get_git_diff():
    return try_subprocess_run(
        ["git", "diff", "--cached"],
        error_msg="Error getting git diff",
    )


def get_staged_files():
    result = try_subprocess_run(
        ["git", "diff", "--name-only", "--cached"],
        error_msg="Error getting staged files",
    )

    files = result.strip().split("\n")
    return [f for f in files if f]  # Filter out empty strings


def get_branch_name():
    return try_subprocess_run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        error_msg="Error getting current branch",
        exit_on_error=True,
    )


def get_commit_history():
    result = try_subprocess_run(
        ["git", "log", "--oneline", "--no-merges", "--max-count=25"],
        error_msg="Error getting branch commit history",
        exit_on_error=False,
    )

    if result is None:
        console.print(
            "[bold yellow]Warning: Could not get branch commits:[/bold yellow]"
        )
        return None
    return result.strip() if result.strip() else None


def truncate_context(context, max_length=25000):
    if len(context) > max_length:
        context = context[:max_length] + "\n[Content truncated due to size...]"
    return context


def assemble_prompt(user_provided_context):
    """Generate a commit message using OpenAI's API."""

    staged_files = get_staged_files()
    if not staged_files:
        console.print("[bold yellow]No staged changes to commit.[/bold yellow]")
        sys.exit(0)
    diff = get_git_diff()
    diff = truncate_context(diff)

    branch_name = get_branch_name()
    commits = get_commit_history()

    context = f"<branch_name>{branch_name}</branch_name>\n"
    if commits:
        context += f"<commit_history>\n{truncate_context(commits)}\n</commit_history>"
    if user_provided_context:
        context += f"<task_context>\n{user_provided_context}\n</task_context>"

    TASK_CONTEXT_SPECIFIC_INSTRUCTIONS = (
        "✅ Ensure the commit message reflects the task context, describing the 'why' or 'what' at a higher level.\n"
        "✅ Where appropriate, enrich the commit message with details of the code change in concrete terms, referencing specific symbols, function names, or key entities modified.\n"
    )
    NO_TASK_CONTEXT_INSTRUCTIONS = (
        "✅ Focus on the diff and commit history to infer the intent behind the changes.\n"
        "✅ If intent isn't obvious, describe the code change in concrete terms, referencing specific symbols, function names, or key entities modified."
    )

    prompt = f"""
<diff>
{diff}
</diff>

Based on the diff context, generate a concise, one-line commit message following these guidelines:

✅ Use conventional commit message style. 
- Types include: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `papercut`, `ci`
- Use a granular but short, abbreviated scope based on the app/feature/component/script/etc. that is being changed. 
- For example, if the change is to the `User` model, the scope could be `user-model`.
{TASK_CONTEXT_SPECIFIC_INSTRUCTIONS if user_provided_context else NO_TASK_CONTEXT_INSTRUCTIONS}
✅ Describe the change concisely. For example, instead of "feat: Update `User` to support `last_login` tracking", write "feat(user-model): Track `last_login`.
✅ Enclose all code-specific terms (like function/method names, variable names, class names, file names) in backticks (e.g., `my_function`, `UserService`).
✅ If multiple distinct changes are present, focus on the primary or most impactful change.
❌ Exclude issue tracker numbers, ticket references, or URLs

<context>
{context}
</context>
"""
    return prompt


def agent_generate_commit_message(
    prompt,
    model,
    max_output_tokens=1024,
):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        console.print(
            "[bold red]Error:[/bold red] OPENAI_API_KEY environment variable not set."
        )
        sys.exit(1)
    base_url = os.environ.get("OPENAI_BASE_URL")
    client = OpenAI(api_key=api_key, base_url=base_url)
    last_error = None
    for attempt in range(1, 4):
        try:
            response = client.responses.parse(
                model=model,
                instructions="Review code and suggest a commit message based on its intention",
                input=prompt,
                text_format=CommitMessage,
                max_output_tokens=max_output_tokens,
                store=False,
            )
        except OpenAIError as e:
            last_error = (
                f"Error calling the model API: {type(e).__name__}: {e}\n"
                f"model={model} base_url={base_url or 'https://api.openai.com/v1 (default)'}"
            )
        else:
            parsed = response.output_parsed
            if parsed is None:
                last_error = (
                    "Model returned no parsable output "
                    f"(status={getattr(response, 'status', 'unknown')}, "
                    f"incomplete_details={getattr(response, 'incomplete_details', None)})."
                )
            elif parsed.not_enough_context:
                return "NOT ENOUGH CONTEXT"
            else:
                message = parsed.message.strip() if parsed.message else ""
                if message:
                    return message
                last_error = "Model returned an empty commit message."

        if attempt < 3:
            console.print(
                f"[bold yellow]Generation attempt {attempt} failed; retrying "
                f"({attempt + 1}/3)...[/bold yellow]"
            )

    console.print(f"[bold red]Error:[/bold red] {last_error}")
    raise SystemExit(1)


def commit_changes(message, flags=None):
    cmd = ["git", "commit", "-m", message] + (flags or [])
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


@click.command(help="Generate commit messages using OpenAI models.")
@click.argument("comments", default="")
@click.option("--model", default="gpt-5.6-luna", help="Model to use for generation.")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Pass --dry-run to git commit (show what would be committed without committing).",
)
@click.option(
    "--no-verify",
    is_flag=True,
    help="Pass --no-verify to git commit (skip pre-commit and commit-msg hooks).",
)
@click.option(
    "-e",
    "--edit",
    is_flag=True,
    help="Pass -e to git commit (open generated message in editor before committing).",
)
def main(comments, model, dry_run, no_verify, edit):
    if not is_git_repository():
        console.print("[bold red]Error:[/bold red] Not in a git repository.")
        sys.exit(1)

    prompt = assemble_prompt(comments)
    commit_message = agent_generate_commit_message(prompt, model=model)

    if commit_message == "NOT ENOUGH CONTEXT":
        console.print(
            "[bold red]Failed to generate commit message. Rerun the script with more context.[/bold red]"
        )
        sys.exit(1)

    console.print(
        Panel(commit_message, title="Generated Commit Message", border_style="green")
    )

    commit_flags = []
    if dry_run:
        commit_flags.append("--dry-run")
    if no_verify:
        commit_flags.append("--no-verify")
    if edit:
        commit_flags.append("-e")

    console.print("[bold cyan]Committing changes...[/bold cyan]")
    if commit_changes(commit_message, commit_flags):
        console.print("[bold green]Successfully committed changes![/bold green]")
    else:
        console.print("[bold red]Failed to commit changes.[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
