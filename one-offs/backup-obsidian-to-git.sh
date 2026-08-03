#!/usr/bin/env bash
set -euo pipefail

SOURCE="$HOME/Obsidian/lens"
TARGET="$HOME/Obsidian/lens-git"

SNAPSHOT_DATE="$(date +%Y-%m-%d_%H-%M-%S)"
COMMIT_MSG="snapshot: ${SNAPSHOT_DATE}"
TAG_NAME="snapshot-${SNAPSHOT_DATE}"

[[ -d "$SOURCE" ]] || { echo "Source does not exist: $SOURCE" >&2; exit 1; }

mkdir -p "$TARGET"
cd "$TARGET"

[[ -d .git ]] || git init

cat > .gitignore <<'EOF'
.DS_Store
Thumbs.db
*.swp
*.tmp
.obsidian/workspace.json
.obsidian/workspace-mobile.json
.trash/
*.sync-conflict*
*conflicted copy*
EOF

rsync -a --delete \
  --exclude='.git/' \
  --exclude='.gitignore' \
  "$SOURCE"/ \
  "$TARGET"/

git add -A

if git diff --cached --quiet; then
  echo "No changes; no commit/tag created."
  exit 0
fi

git commit -m "$COMMIT_MSG"
git tag -a "$TAG_NAME" -m "$COMMIT_MSG"

echo "Committed and tagged: $TAG_NAME"
echo "Done."
echo "To copy back, run:"
echo "rsync -a --delete $TARGET/ $SOURCE/ --exclude .git"