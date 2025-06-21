#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "openai",
#   "rich",
# ]
# ///

import os
import subprocess
import sys
import argparse
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress
from openai import OpenAI

console = Console()


def try_subprocess_run(args, *, error_msg, exit_on_error=True):
    try:
        result = subprocess.run(
            args,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
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
            f"[bold yellow]Warning: Could not get branch commits:[/bold yellow]"
        )
        return None
    return result.strip() if result.strip() else None


def stage_all_changes():
    result = try_subprocess_run(
        ["git", "add", "-A"], error_msg="Error staging changes", exit_on_error=False
    )
    return result is not None

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
- Types include: feat, fix, docs, style, refactor, test, chore. 
- Use a granular but short, abbreviated scope based on the app/feature/component/script/etc. that is being changed. 
- For example, if the change is to the `User` model, the scope could be `user-model`.
{TASK_CONTEXT_SPECIFIC_INSTRUCTIONS if user_provided_context else NO_TASK_CONTEXT_INSTRUCTIONS}
✅ Describe the change concisely. For example, instead of "feat: Update `User` to support `last_login` tracking", write "feat(user-model): Track `last_login`.
✅ Enclose all code-specific terms (like function/method names, variable names, class names, file names) in backticks (e.g., `my_function`, `UserService`).
✅ If multiple distinct changes are present, focus on the primary or most impactful change.
❌ Exclude issue tracker numbers, ticket references, or URLs

Only write the commit message, or NOT ENOUGH CONTEXT if the meaning of the changes is not clear.

<context>
{context}
</context>
"""
    return prompt


def agent_generate_commit_message(prompt, max_completion_tokens=250, temperature=0.0):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        console.print(
            "[bold red]Error:[/bold red] OPENAI_API_KEY environment variable not set."
        )
        sys.exit(1)
    client = OpenAI(api_key=api_key)
    with Progress() as progress:
        task = progress.add_task("[cyan]Generating commit message...", total=1)

        try:
            response = client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an experienced developer. "
                        "Having just written some code, you are now committing that code to git.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=max_completion_tokens,
                temperature=temperature,
            )

            progress.update(task, completed=1)

            commit_message = response.choices[0].message.content.strip()
            return commit_message

        except Exception as e:
            progress.update(task, completed=1)
            console.print(
                f"[bold red]Error generating commit message:[/bold red] {str(e)}"
            )
            return None


def commit_changes(message):
    result = try_subprocess_run(
        ["git", "commit", "-m", message],
        error_msg="Error committing changes",
        exit_on_error=False,
    )
    return result is not None


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Generate commit messages using OpenAI's GPT-4o model."
    )
    parser.add_argument(
        "comments",
        nargs="?",
        default="",
        help="User comments to include in the commit message generation prompt",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate commit message without actually committing",
    )
    return parser.parse_args()


def main():
    args = parse_arguments()

    if not is_git_repository():
        console.print("[bold red]Error:[/bold red] Not in a git repository.")
        sys.exit(1)

    prompt = assemble_prompt(args.comments)
    commit_message = agent_generate_commit_message(prompt)

    if commit_message == "NOT ENOUGH CONTEXT":
        console.print(
            "[bold red]Failed to generate commit message. Rerun the script with more context.[/bold red]"
        )
        sys.exit(1)

    if not commit_message:
        console.print(
            "[bold red]Failed to generate commit message. Using default message.[/bold red]"
        )
        commit_message = "Update code based on recent changes"

    console.print(
        Panel(commit_message, title="Generated Commit Message", border_style="green")
    )

    if args.dry_run:
        console.print("[bold yellow]Dry run mode: Changes not committed.[/bold yellow]")
        return

    console.print("[bold cyan]Committing changes...[/bold cyan]")
    if commit_changes(commit_message):
        console.print("[bold green]Successfully committed changes![/bold green]")
    else:
        console.print("[bold red]Failed to commit changes.[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
