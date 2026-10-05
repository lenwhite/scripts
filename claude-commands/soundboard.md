---
description: Act as a sounding board / sanity check without taking actions
argument-hint: "[query]"
---
Act as a sounding board / sanity check for the following query, without taking any actions:

---
$ARGUMENTS
---

Systemmatically:

- State your immediate intuition, making as few assumptions as possible, then:
- If needed, explore the codebase (using balanced subagents, in parallel) for more context and/or to verify user assumptions.
    - Unless specifically asked for, exclude plan files, test files or git history for context. Take the codebase as the source of truth.
- If needed, Ask clarifying questions based on the exploration to clarify user intent or assumptions
    - If you have questions, wait for the user to clarify before proceeding with proposals
- Based on the above steps, list down a few proposals or options
- Give your recommendations based on the proposals or options
