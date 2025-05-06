#!/bin/zsh

if [[ $(pwd) != *"/projects/instawork"* ]]; then
    echo "You must be in the instawork project directory to run this command"
    return
fi
docker compose --ansi=always logs -n 10 -f backend frontend | while IFS= read -r line; do
echo $line
if [[ "$line" == *"Quit the server with CONTROL-C."* ]]; then
    afplay /System/Library/Sounds/Funk.aiff
fi
if [[ "$line" == *"compiled"* ]]; then
    afplay /System/Library/Sounds/Funk.aiff
fi
done