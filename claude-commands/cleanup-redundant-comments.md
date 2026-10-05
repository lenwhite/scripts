---
description: Remove redundant comments from changed files via per-file subagents
argument-hint: "[files/areas]"
---
Review files to clean up the code by removing any redundant comments. Redundant comments are comments that restate the code itself, or are likely to drift from the code (e.g. documenting *how* a function is used in other areas of the codebase).

Remove *all comments* except:
- TODOs (and other comments indicating areas for future work/improvement)
- Comments that indicate temporary workarounds and hacks 
- Comments that visually separate long sections of code
- Comments that refer to details outside the codebase (e.g. tickets, external doc)
- Comments that state something *deeply unintuitive*

**For docstrings**, remove param or return type specifications where covered by type hints. Delete type hints entirely where the name is self explanatory or the implementation is trivial.

Don't review it yourself. Always invoke one subagent per changed file to review (and clean it up if needed). There is no need to verify the subagent's work. 

Instruct the subagent to:
- Make ONLY changes to comments added/changed in this diff. (unless overridden below)
- Assume the readers are highly proficient with the programming language. 
- Bias towards removal.


---
Additional context / files or areas to focus on (if any): $ARGUMENTS
