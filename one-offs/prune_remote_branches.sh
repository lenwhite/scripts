#!/bin/bash

# Prompt user for branch prefix
echo -n "Enter branch prefix: "
read prefix

# Fetch latest branches
git fetch --prune

# Get list of remote branches matching the prefix
branches=$(git branch -r | grep "origin/$prefix" | sed 's/origin\///')

# Check if any branches match
if [ -z "$branches" ]; then
    echo "No remote branches found with prefix '$prefix'."
    exit 0
fi

count=$(echo "$branches" | wc -l)
echo "Found $count remote branches with prefix '$prefix':"


# Iterate through each matching branch
for branch in $branches; do
    last_commit_date=$(git show -s --format=%ci origin/$branch)
    echo -n "Do you want to delete remote branch '$branch' (last commit: $last_commit_date)? (y/n): "
    read answer
    if [ "$answer" == "y" ]; then
        git push origin --delete "$branch"
        echo "Deleted remote branch: $branch"
    else
        echo "Skipped: $branch"
    fi
done
