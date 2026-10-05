---
description: Review the current branch with a subagent, then address the findings with judgment
argument-hint: "[subagent tier] [focus areas]"
---
Perform a code review of the current git branch using a subagent, then act on the findings with your own judgment.

Default review focus (unless overridden below): **simplification**, **overly defensive programming** (unnecessary null checks, redundant guards, impossible fallbacks), **unnecessary abstractions** (over-engineering, premature generalization, needless indirection, YAGNI), and **dead/redundant code**. Reviewer should disregard git history unless otherwise instructed.

## Instructions

1. **Establish the diff range.** Find the merge-base against trunk (`git merge-base HEAD origin/main`, falling back to `origin/master`/`main`/`master`). Use this exact commit in the subagent prompt.
2. **Launch the review subagent** (default: balanced). Give it a self-contained prompt: run `git diff <merge-base> HEAD`, apply the focus areas, and for each finding report file path + snippet, the issue, and a concrete suggested change as a prioritized list (High/Medium/Low). Tell it **review only — no edits.**
3. **Validate every finding yourself.** Read the code, confirm the issue is real and the fix is correct (including library behavior and truly-unreachable "dead code"). Reject or adapt anything subtly wrong, noting why.
4. **Apply accepted changes** with precise edits; clean up now-unused imports/props/files.
5. **Verify.** Type-check, lint touched paths, run relevant tests — all green.
6. **Summarize** each finding with your decision (Fixed / Adapted / Rejected + why) and verification results.

---
Subagent and/or focus areas to override the defaults (if any): $ARGUMENTS
