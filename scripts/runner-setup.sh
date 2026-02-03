#!/bin/bash
# GitHub Actions Self-Hosted Runner Setup Script
# Run this on the target server after server-setup.sh

set -e

RUNNER_VERSION="2.321.0"  # Update to latest version
RUNNER_DIR="/opt/actions-runner"

echo "=== GitHub Actions Runner Setup ==="

# Check if GITHUB_TOKEN is set
if [ -z "$GITHUB_REPO" ]; then
    echo "Please set GITHUB_REPO environment variable"
    echo "Example: export GITHUB_REPO=username/delta-to-json"
    exit 1
fi

if [ -z "$GITHUB_TOKEN" ]; then
    echo "Please set GITHUB_TOKEN environment variable (with repo scope)"
    echo "Get a token from: https://github.com/settings/tokens/new"
    exit 1
fi

# Create runner directory
echo "[1/4] Creating runner directory..."
sudo mkdir -p $RUNNER_DIR
sudo chown $USER:$USER $RUNNER_DIR
cd $RUNNER_DIR

# Download runner
echo "[2/4] Downloading GitHub Actions runner..."
curl -o actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz -L \
    https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz

tar xzf actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz
rm actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz

# Get registration token
echo "[3/4] Getting registration token..."
REG_TOKEN=$(curl -s -X POST \
    -H "Accept: application/vnd.github+json" \
    -H "Authorization: Bearer $GITHUB_TOKEN" \
    https://api.github.com/repos/$GITHUB_REPO/actions/runners/registration-token | jq -r '.token')

if [ "$REG_TOKEN" == "null" ] || [ -z "$REG_TOKEN" ]; then
    echo "Failed to get registration token. Check your GITHUB_TOKEN permissions."
    exit 1
fi

# Configure runner
echo "[4/4] Configuring runner..."
./config.sh --url https://github.com/$GITHUB_REPO \
    --token $REG_TOKEN \
    --name "prod-server" \
    --labels "self-hosted,Linux,X64,production" \
    --work "_work" \
    --unattended

# Install as service
echo "Installing runner as systemd service..."
sudo ./svc.sh install
sudo ./svc.sh start

echo ""
echo "=== Runner Setup Complete ==="
echo "Runner is now running as a systemd service"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status actions.runner.*.service  # Check status"
echo "  sudo systemctl restart actions.runner.*.service # Restart"
echo "  sudo ./svc.sh stop && sudo ./svc.sh uninstall   # Uninstall"
