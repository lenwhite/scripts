#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check for --dry-run flag
DRY_RUN=false
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
    echo -e "${YELLOW}Running in dry-run mode - no branches will be deleted${NC}"
fi

echo -e "${YELLOW}Fetching latest changes from remote...${NC}"
git fetch --prune

# Switch to master branch and update it
echo -e "${YELLOW}Updating master branch...${NC}"
git checkout master
git pull origin master

# Get list of all local branches except master
branches=$(git for-each-ref --format='%(refname:short)' refs/heads/ | grep -v '^master$')

echo -e "${YELLOW}Analyzing branches...${NC}"

for branch in $branches; do
    # Skip if branch is master
    [ "$branch" = "master" ] && continue
    
    # Check if branch is merged traditionally
    if git branch --merged master | grep -q "^[* ]*$branch$"; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${GREEN}Would delete branch '$branch' (traditionally merged)${NC}"
        else
            echo -e "${GREEN}Branch '$branch' is merged traditionally - will be deleted${NC}"
            git branch -d "$branch"
        fi
        continue
    fi
    
    # Find the common ancestor (merge-base) between the branch and master
    merge_base=$(git merge-base master "$branch")
    
    # Create a temporary commit with the squashed changes
    squashed_tree=$(git commit-tree "$branch^{tree}" -p "$merge_base" -m "Temporary squash commit")
    
    # Check if this commit's changes exist in master's history
    if git cherry master "$squashed_tree" | grep -q "^-"; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${GREEN}Would delete branch '$branch' (squash-merged)${NC}"
        else
            echo -e "${GREEN}Branch '$branch' appears to be squash-merged - will be deleted${NC}"
            git branch -D "$branch"
        fi
    else
        echo -e "${RED}Branch '$branch' is not merged - keeping${NC}"
    fi
done

echo -e "${YELLOW}Done pruning branches!${NC}"
