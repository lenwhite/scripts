---
description: Implement a plan file end-to-end via subagents, then clean up comments/tests/TS nits and review the staged diff
argument-hint: "[extra instructions]"
---
Implement the plan end-to-end using subagents, then run the cleanup and review passes below **in order**. At all stages:
- minimize the amount of file reads you yourself do
- don't check any subagent's work
- instruct subagents to never spawn subagents

Plan file: **$1**

**Reusing existing workflows:** stages 3, 4, 5 and 6 reuse other prompt templates. Read the template body from `<name>.md` in the same directory as this template, strip the frontmatter and the trailing arguments line (after the final `---`), and paste it into the subagent prompt together with the concrete file list for this run.

## Stage 1 — Implement

1. Read `$1` yourself so you can sanity-check the result later. Record the pre-existing git state (`git status --porcelain`, `git stash list`) so you can tell plan changes apart from prior work.
2. Spawn **one** strong subagent told to: read the plan at the absolute path, implement it fully, and report what it changed plus any deviations. It may edit files; it must not commit, push, or stage.

## Stage 2 — Stage

`git add -A` the files touched by the implementation (do not sweep in unrelated pre-existing changes). From here on, **the staged set is the working scope** — recompute it with `git diff --cached --name-only` at the start of each stage.

## Stage 3 — Redundant comments (only if comments were added)

Check `git diff --cached -U0 | grep '^+'` for added/changed comment lines. If there are none, skip this stage and say so.

If there are: run the **cleanup-redundant-comments** workflow. Follows that template's rule of one subagent per changed file — spawn them in parallel across files (use balanced subagents), each scoped to a single file and to comments touched by this diff only.

## Stage 4 — Tests (only if tests were added/changed)

If the staged set contains test files (`*.test.*`, `*.spec.*`, `tests/**`), run the **improve-tests** workflow **once** with a strong subagent, scoped to exactly those staged test files. Otherwise skip and say so.

## Stage 5 — Stage, then TypeScript nits (only if TS files changed)

1. `git add -A` the touched files again.
2. If the staged set contains `.ts`/`.tsx` files, run the **cleanup-ts-nits** workflow with a strong subagent, scoped to exactly those staged TS files. Otherwise skip and say so.
3. `git add -A` the touched files again.

## Stage 6 — Review the staged diff

Run the **review-branch** workflow with a strong subagent, but **targeting the staged changes only**: the subagent reviews `git diff --cached` (not a merge-base range) and reviews only — no edits. Strictly scope the review to simplification, overly defensive programming, unnecessary abstractions, dead/redundant code. The subagent should output its finding into a review file. There's no need to prompt the subagent to check for correctness.

## Stage 7 - Apply review

Then, instead of validating the findings yourself, spawn a strong subagent to validate and apply the review findings. Do NOT stage the final changes.

---
Extra instructions / subagent tier overrides / areas to focus on (if any): $ARGUMENTS
