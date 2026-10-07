---
name: write-short-plan
description: Produce a high-level plan file (background, decisions, architecture/invariants, files)
argument-hint: "[topic / focus]"
---
Produce a plan file for the work we've been discussing. Hand off any exploration done, decisions made, constraint decided on to a strong subagent, who will produce a plan file to the following specifications:

<plan-specs>

## Audience

Write handling off the work to a competent senior engineer fresh to the work, without context of this conversation. That engineer can read the codebase, so don't restate what the code already says. Trust the engineer to make solid decisions.

Anything decided, discovered, or ruled out here that isn't written down is lost.

The test for every line: *would omitting this cause the implementer to make a wrong or arbitrary choice?* If no, cut it.

## Structure

Use exactly these four sections, in this order.

### 1. Background & context

Why this work exists. The problem or current behaviour, who/what it affects, and the trigger. Include non-obvious context uncovered during exploration or debugging — the bug's actual root cause, a surprising constraint, a subsystem that behaves differently than expected. Keep to a few short paragraphs or bullets.

### 2. Decisions made

The choices that are now settled, each with a one-line rationale. Include options that were **considered and rejected**, with the reason — this is what stops the implementer from relitigating them.

State scope boundaries here too: what is explicitly *not* part of this work.

If something is genuinely unresolved, list it as `OPEN:` with the shortlist of options and what would decide it. Do not disguise an open question as a decision.

### 3. Architecture

The intended logic flow end-to-end: entry point → transformations → side effects → outputs. Name the concrete modules, functions, types, tables, or routes involved so the implementer can find them, but describe *behaviour*, not line edits.

Add diagrams where helpful. State abstraction boundaries clearly - what each class/function is responsible for, and its proposed interface.

### 4. Files to reference

A flat list of paths with a few words on each: what it is and why it matters (to change, to mirror as a pattern, or to read for context). Mark new files as `(new)`. No per-file task breakdowns.

## Keep out

- Step-by-step edit instructions, pseudo-diffs, or long code blocks. Short signature/type/shape sketches are fine when the shape *is* the decision.
- Testing, linting, build, or CI steps.
- Effort estimates, phases, timelines, checklists of subtasks.
- Restating code that the implementer will read anyway.
- Hedging ("we could maybe consider…") — either decide it or mark it `OPEN:`.

## Process

Plan the document's content before writing it. Do not gather new context unless something needed for a section is genuinely missing; prefer what's already in this conversation. Do not start implementing.

Unless otherwise specified, place it in CWD.

After writing the plan - do an additional editing pass for brevity and clarity.

</plan-specs>

After the subagent produces this plan file - briefly review and check that it matches your understanding.
