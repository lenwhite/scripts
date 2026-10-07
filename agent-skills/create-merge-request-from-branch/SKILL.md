---
name: create-merge-request-from-branch
description: Create a draft merge/pull request from the current branch
argument-hint: "[scope/issue/title hints]"
---
Create a merge request from the branch.

## Detailed Instructions

- check git status
    - if we're on `main` and there's unstaged changes - stash, create a feature branch and commit the staged changes
    - otherwise, if we're already on a feature branch, examine the git history for context
- ask the user for context if it's not obvious from the commit history
- use the hosting platform's CLI for all MR/PR operations - infer which one from context (git remote, CI config, which CLI is authenticated)
- list the current user's previously merged merge requests as a reference. if there are no merge requests from this author, use other authors as a reference
- retrieve details of 3 previous merge requests as a reference
- never give a detailed breakdown of code-level changes in the MR, beyond a short summary
- before creating the MR, find the pipeline's linting/formatting/test rules (e.g. `.gitlab-ci.yml` / `.github/workflows/*` and any included CI files, `package.json` scripts, lint/format/test configs) and run them locally. Fix any failures (commit and push the fixes) and only proceed once they all pass
- create the mr as a draft, with a title and description, set the author as a reviewer `@me`(placeholder, set reviewer if self-review not supported)

## Example 1 - On `main` with unstaged changes (GitLab)

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

## Example 2 — Already on a feature branch, history is clear (GitHub)


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

# Reference past PRs by author
gh pr list --state merged --author @me
# If empty, fallback:
gh pr list --state merged

# View 3 prior PRs to mirror format/sections
gh pr view <number>
gh pr view <number>
gh pr view <number>

# Find and run the pipeline's lint/format/test rules, fix failures, then commit + push
cat .github/workflows/*.yml
cat package.json
yarn lint && yarn format:check && yarn test
git add -A && git commit -m "chore: fix lint/format/test failures" && git push

# Create draft PR
gh pr create --draft \
  --title "feat(profile): avatar upload with client-side validation" \
  --body "..."
```
