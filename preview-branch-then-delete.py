#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "rich",
# ]
# ///

import subprocess
import argparse
import sys
from rich.console import Console

console = Console()


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Preview a branch squash merge and optionally delete it."
    )
    parser.add_argument(
        "branch_name", type=str, help="Branch name to preview and potentially delete."
    )
    return parser.parse_args()


def run_git_command(
    command, error_message="Git command failed", expected_return_codes=[0]
):
    """Run a git command and handle errors."""
    try:
        # Remove check=True, capture output, handle return code manually
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8"
        )

        if result.returncode not in expected_return_codes:
            console.print(f"[bold red]Error:[/bold red] {error_message}")
            console.print(f"[red]Command:[/red] {' '.join(command)}")
            console.print(f"[red]Return Code:[/red] {result.returncode}")
            if result.stderr:
                console.print(f"[red]Stderr:[/red] {result.stderr.strip()}")
            if result.stdout:
                console.print(f"[red]Stdout:[/red] {result.stdout.strip()}")
            sys.exit(1)  # Exit if git command has unexpected return code

        return result  # Return the result object for further inspection
    except FileNotFoundError:
        console.print(
            "[bold red]Error:[/bold red] Git command not found. Is Git installed and in your PATH?"
        )
        sys.exit(1)


def preview_branch(branch_name):
    """Preview the branch by running `git merge --squash --no-commit --strategy-option theirs <branch_name>`"""
    console.print(
        f"Attempting to preview branch '[bold cyan]{branch_name}[/bold cyan]' by applying a squash merge..."
    )
    console.print(
        "[yellow]This will modify your working directory. Check the changes with 'git status' or 'git diff'.[/yellow]"
    )

    # Allow return codes 0 (success) and 1 (conflicts)
    result = run_git_command(
        [
            "git",
            "merge",
            "--squash",
            "--no-commit",
            "--strategy-option",
            "theirs",
            branch_name,
        ],
        error_message=f"Failed to preview branch '{branch_name}'. Does it exist?",
        expected_return_codes=[0, 1],
    )

    if result.returncode == 0:
        console.print(
            "[green]Preview successful. Working directory updated cleanly.[/green]"
        )
    elif result.returncode == 1 and "Automatic merge failed" in result.stdout:
        console.print(
            "[yellow]Preview generated merge conflicts.[/yellow] Please inspect the conflicts in your working directory."
        )
        # Optionally print the conflict details if needed, though git status is better
        # console.print(f"[dim]Output:\\n{result.stdout}[/dim]")
    # Note: If return code was 1 but "Automatic merge failed" wasn't in stdout,
    # run_git_command would have already exited because 1 wasn't in the default expected_return_codes=[0]
    # So we don't strictly need an 'else' here to catch other non-zero codes for this specific call,
    # but it was added previously for robustness in case expected_return_codes was broader.
    # Let's keep the structure simple for now.


def delete_branch(branch_name):
    """Delete the branch by running `git branch -D <branch_name>`"""
    console.print(f"Deleting branch '[bold cyan]{branch_name}[/bold cyan]'...")
    run_git_command(
        ["git", "branch", "-D", branch_name],
        error_message=f"Failed to delete branch '{branch_name}'.",
    )
    console.print(
        f"[green]Branch '[bold cyan]{branch_name}[/bold cyan]' deleted successfully.[/green]"
    )


def git_reset_hard():
    """Reset the current branch to the latest commit (HEAD)"""
    console.print("Resetting working directory to HEAD ('git reset --hard')...")
    run_git_command(
        ["git", "reset", "--hard"],
        error_message="Failed to reset the working directory.",
    )
    console.print("[green]Working directory reset.[/green]")


def main():
    args = parse_arguments()
    branch_name = args.branch_name
    delete_confirmed = False
    try:
        preview_branch(branch_name)

        # Ask for confirmation
        confirm = input(
            f"Delete branch '{branch_name}' after reviewing the preview? (y/n): "
        ).lower()
        if confirm == "y":
            delete_confirmed = True
        else:
            console.print("[yellow]Branch deletion cancelled.[/yellow]")

    finally:
        # Always reset after preview attempt, regardless of confirmation or errors during preview/confirmation
        git_reset_hard()

    # Only delete if confirmed *and* reset was successful (implied by reaching this point)
    if delete_confirmed:
        delete_branch(branch_name)


if __name__ == "__main__":
    main()
