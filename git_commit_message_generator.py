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


def is_git_repository():
    """Check if the current directory is a git repository."""
    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def get_git_diff():
    """Get the git diff of staged changes."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        return result.stdout
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Error getting git diff:[/bold red] {e.stderr}")
        sys.exit(1)


def get_staged_files():
    """Get a list of staged files."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--cached"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        files = result.stdout.strip().split("\n")
        return [f for f in files if f]  # Filter out empty strings
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Error getting staged files:[/bold red] {e.stderr}")
        sys.exit(1)


def get_current_branch():
    """Get the name of the current branch."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Error getting current branch:[/bold red] {e.stderr}")
        return "unknown-branch"


def get_branch_commits():
    """Get the git log entries for the current branch up to where it branches from master."""
    try:
        merge_base_result = subprocess.run(
            ["git", "merge-base", "master", "HEAD"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        merge_base = merge_base_result.stdout.strip()

        log_result = subprocess.run(
            ["git", "log", f"{merge_base}..HEAD", "--oneline"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        return log_result.stdout.strip()
    except subprocess.CalledProcessError as e:
        console.print(
            f"[bold yellow]Warning: Could not get branch commits:[/bold yellow] {e.stderr}"
        )
        return ""


def stage_all_changes():
    """Stage all changes."""
    try:
        subprocess.run(
            ["git", "add", "-A"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Error staging changes:[/bold red] {e.stderr}")
        return False


def generate_commit_message(diff_text, branch_name, branch_commits, user_comments="None"):
    """Generate a commit message using OpenAI's API."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        console.print(
            "[bold red]Error:[/bold red] OPENAI_API_KEY environment variable not set."
        )
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    max_diff_length = 50000
    if len(diff_text) > max_diff_length:
        diff_text = diff_text[:max_diff_length] + "\n[Diff truncated due to size...]"

    branch_context = f"Current branch: {branch_name}\n"
    if branch_commits:
        branch_context += f"Commit history on this branch:\n{branch_commits}\n"

    prompt = f"""
<context>
{branch_context}
</context>

<diff>
{diff_text}
</diff>

Based on the changes and branch context, generate a concise, one-line commit message following these guidelines:

1.  **Prioritize inferring the overall intent** of the changes from the diff and branch context. If the intent is clear, use it to describe the "why" or "what" at a higher level.
2.  If intent isn't obvious, **describe the most significant concrete change**, referencing specific symbols, function names, or key entities modified.
3.  **Start with an imperative verb** describing the action (e.g., "Add", "Remove", "Correct", "Implement", "Simplify").
    * Describe the change directly. For example, instead of "Update `User` to support `last_login`", write "Support `last_login` in `User` model".
    * Avoid generic leading words like "Update", "Refactor", or "Enhance" unless they specifically describe the primary action in a way that's more descriptive than the alternative (e.g. "Refactor `complex_function` for clarity").
4.  **Enclose all code-specific terms** (like function/method names, variable names, class names, file names) in backticks (e.g., \`my\_function\`, \`UserService\`).
5.  **Strive for brevity while ensuring the message clearly communicates the core change.** 
6.  **Aim for a single, impactful line.** While there's no strict character limit, the message should not become a paragraph.
7.  If multiple distinct changes are present, **focus the message on the primary or most impactful change.**
8.  **Exclude issue tracker numbers, ticket references, or URLs** from the commit message itself.


Only write the commit message, nothing else.

<user_comments>
{user_comments}
</user_comments>
"""

    with Progress() as progress:
        task = progress.add_task("[cyan]Generating commit message...", total=1)

        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an experienced developer. "
                        "Having just written some code, you are now committing that code to git."
                    },
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=150,
                temperature=0.1,
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
    """Commit changes with the given message."""
    try:
        subprocess.run(
            ["git", "commit", "-m", message],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Error committing changes:[/bold red] {e.stderr}")
        return False


def parse_arguments():
    """Parse command line arguments."""
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

    staged_files = get_staged_files()
    if not staged_files:
        console.print("[bold yellow]No staged changes to commit.[/bold yellow]")
        console.print(
            "[bold cyan]Tip:[/bold cyan] Use 'git add <file>' to stage changes before running this script."
        )
        sys.exit(0)

    console.print(f"[bold green]Found {len(staged_files)} staged files.[/bold green]")

    console.print("[bold cyan]Getting git diff of staged changes...[/bold cyan]")
    diff = get_git_diff()

    if not diff.strip():
        console.print("[bold yellow]No changes detected in staged files.[/bold yellow]")
        sys.exit(0)

    console.print("[bold cyan]Getting branch information...[/bold cyan]")
    branch_name = get_current_branch()
    console.print(f"[bold green]Current branch: {branch_name}[/bold green]")

    branch_commits = get_branch_commits()
    if branch_commits:
        console.print("[bold green]Found commit history for this branch[/bold green]")

    commit_message = generate_commit_message(diff, branch_name, branch_commits, args.comments)

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
