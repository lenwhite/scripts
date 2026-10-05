---
description: Create a draft merge request from the current branch using glab
argument-hint: "[scope/issue/title hints]"
---
Create a merge request from the branch.

## Detailed Instructions

- check git status
    - if we're on `main` and there's unstaged changes - stash, create a feature branch and commit the staged changes
    - otherwise, if we're already on a feature branch, examine the git history for context
- ask the user for context if it's not obvious from the commit history
- run `glab mr list --merged --author <username>` (current GitLab user, from `glab auth status`) to list the previous merge requests as a reference. if there are no merge requests from this author, use other authors as a reference `glab mr list --merged` 
- use `glab mr view <number>` to retrieve details of 3 previous merge requests as a reference
- never give a detailed breakdown of code-level changes in the MR, beyond a short summary
- before creating the MR, find the pipeline's linting/formatting/test rules (e.g. `.gitlab-ci.yml` and any included CI files, `package.json` scripts, lint/format/test configs) and run them locally. Fix any failures (commit and push the fixes) and only proceed once they all pass
- create the mr with `glab mr create --draft --title <title> --description <description>` with `<username>` as reviewer (as a placeholder)

## Example 1 - On `main` with unstaged changes

```bash
# 1) Check git status
git status
# Output indicates: On branch main; changes not staged for commit; some files modified

# 2) Stash unstaged changes
git stash -u

# 3) Create and switch to a feature branch
git checkout -b feature/add-logging

# 4) Bring back the stash if needed
git stash pop
# Stage selectively as needed
git add src/logger.ts
git commit -m "feat(logging): add structured logger and request IDs"
# Sync to remote
git push -U origin feature/add-logging

# 5) Examine commit history for context
git log --oneline -n 10

# 6) If context is unclear, ask the user
# (Prompt): “What’s the scope for the logging change? Any linked issue or MR template?”

# 7) List merged MRs by author
glab mr list --merged --author <username>
# If none found:
glab mr list --merged

# 8) View details of 3 previous MRs for reference
glab mr view <number>
glab mr view <number>
glab mr view <number>

# 9) Find and run the pipeline's lint/format/test rules, fix failures, then commit + push
cat .gitlab-ci.yml            # plus any `include:`d CI files
cat package.json              # check the scripts section
yarn lint && yarn format:check && yarn test
# fix any issues, then:
git add -A && git commit -m "chore: fix lint/format/test failures" && git push

# 10) Create the draft MR (use title/description derived from commit + references)
glab mr create --draft \
  --title "feat(logging): structured logger + request correlation IDs" \
  --description "..."
```

## Example 2 — Already on a feature branch, history is clear


```bash

# Check status (we're already on a feature branch)
git status
# Output: On branch feature/user-profile-avatar; working tree clean
# Sync to remote
git push

# Examine history for context
git log --oneline -n 5
# Example commit:
# 9c1a3de feat(profile): enable avatar upload with client-side validation

# Reference past MRs by author
glab mr list --merged --author <username>
# If empty, fallback:
glab mr list --merged

# View 3 prior MRs to mirror format/sections
glab mr view <number>
glab mr view <number>
glab mr view <number>

# Find and run the pipeline's lint/format/test rules, fix failures, then commit + push
cat .gitlab-ci.yml
cat package.json
yarn lint && yarn format:check && yarn test
git add -A && git commit -m "chore: fix lint/format/test failures" && git push

# Create draft MR
glab mr create --draft \
  --title "feat(profile): avatar upload with client-side validation" \
  --description "..."
```


---
Additional context for the MR — scope, linked issue, title/description hints (if any): $ARGUMENTS
