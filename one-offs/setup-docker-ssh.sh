#!/bin/bash

# setup-docker-ssh.sh
# Script to set up SSH authentication in a Docker container for GitHub access
# Usage: ./setup-docker-ssh.sh [container_name]
# Default container name: frontend

# Enable error handling
set -e

# Function for logging messages
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >&2
}

# Function for logging errors
error() {
    log "ERROR: $1"
    exit 1
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Default container name
CONTAINER=${1:-frontend}
SERVICE_NAME=$(echo "$CONTAINER" | sed 's/^instawork-//')

log "Setting up SSH for container: $CONTAINER (service: $SERVICE_NAME)"

# Check if docker compose is installed
if ! command_exists docker; then
    error "Docker is not installed. Please install Docker first."
fi

# Check if SSH keys exist
SSH_KEY_PATH="$HOME/.ssh"
SSH_PRIVATE_KEY=""

log "Checking for SSH keys..."

if [ -f "$SSH_KEY_PATH/id_ed25519" ]; then
    SSH_PRIVATE_KEY="$SSH_KEY_PATH/id_ed25519"
    SSH_PUBLIC_KEY="$SSH_KEY_PATH/id_ed25519.pub"
    log "Found Ed25519 SSH key."
elif [ -f "$SSH_KEY_PATH/id_rsa" ]; then
    SSH_PRIVATE_KEY="$SSH_KEY_PATH/id_rsa"
    SSH_PUBLIC_KEY="$SSH_KEY_PATH/id_rsa.pub"
    log "Found RSA SSH key."
else
    error "No SSH key found. Please generate an SSH key pair using 'ssh-keygen' first."
fi

# Verify the container exists and is running
log "Verifying container status..."
if ! docker compose ps --format "{{.Name}}" | grep -q "^$CONTAINER$"; then
    error "Container '$CONTAINER' is not running. Please start it first."
fi

# Create .ssh directory in the container
log "Creating .ssh directory in the container..."
if ! docker compose exec "$SERVICE_NAME" mkdir -p /root/.ssh/; then
    error "Failed to create .ssh directory in container."
fi

# Copy SSH private key to container
log "Copying SSH private key to container..."
if ! docker compose cp "$SSH_PRIVATE_KEY" "$SERVICE_NAME:/root/.ssh/"; then
    error "Failed to copy private key to container."
fi

# Copy SSH public key to container (if it exists)
if [ -f "$SSH_PUBLIC_KEY" ]; then
    log "Copying SSH public key to container..."
    if ! docker compose cp "$SSH_PUBLIC_KEY" "$SERVICE_NAME:/root/.ssh/"; then
        error "Failed to copy public key to container."
    fi
fi

# Set correct permissions for SSH keys
log "Setting correct permissions for SSH keys..."
BASENAME=$(basename "$SSH_PRIVATE_KEY")
PUBLIC_BASENAME=$(basename "$SSH_PUBLIC_KEY")
if ! docker compose exec "$SERVICE_NAME" chmod 600 "/root/.ssh/$BASENAME"; then
    error "Failed to set permissions for private key."
fi

if [ -f "$SSH_PUBLIC_KEY" ]; then
    if ! docker compose exec "$SERVICE_NAME" chmod 644 "/root/.ssh/$PUBLIC_BASENAME"; then
        error "Failed to set permissions for public key."
    fi
fi

# Add GitHub's host key to known_hosts
log "Adding GitHub's host key to known_hosts..."
if ! docker compose exec "$SERVICE_NAME" sh -c "ssh-keyscan github.com >> /root/.ssh/known_hosts"; then
    error "Failed to add GitHub's host key to known_hosts."
fi

# Set correct permissions for known_hosts
log "Setting correct permissions for known_hosts..."
if ! docker compose exec "$SERVICE_NAME" chmod 644 /root/.ssh/known_hosts; then
    error "Failed to set permissions for known_hosts."
fi

# Test the SSH connection to GitHub
log "Testing SSH connection to GitHub..."
if docker compose exec "$SERVICE_NAME" ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
    log "SSH authentication successful!"
else
    # Don't error out here as the command always returns a non-zero exit code
    # Instead, check if it looks like a successful authentication response
    GITHUB_OUTPUT=$(docker compose exec "$SERVICE_NAME" ssh -T git@github.com 2>&1)
    if echo "$GITHUB_OUTPUT" | grep -q "Hi "; then
        log "SSH authentication successful!"
    else
        log "WARNING: SSH authentication might have issues. Please check the output below:"
        echo "$GITHUB_OUTPUT"
        log "The SSH key in the container may not be added to your GitHub account."
        log "Check your SSH keys at https://github.com/settings/keys"
    fi
fi

log "SSH setup complete for container '$CONTAINER'"
log "You should now be able to use Git with SSH authentication inside the container"

# Make script executable
chmod +x ~/scripts/setup-docker-ssh.sh

