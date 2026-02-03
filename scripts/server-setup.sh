#!/bin/bash
# Server Setup Script for Delta-to-JSON Deployment
# Run this on the target server (ubuntu@192.168.100.106)

set -e

echo "=== Delta-to-JSON Server Setup ==="

# Update system
echo "[1/5] Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# Install Docker
echo "[2/5] Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker $USER
    echo "Docker installed. You may need to re-login for group changes."
else
    echo "Docker already installed: $(docker --version)"
fi

# Install Docker Compose
echo "[3/5] Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    sudo apt-get install -y docker-compose-plugin
    # Also install standalone for compatibility
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi
echo "Docker Compose version: $(docker compose version 2>/dev/null || docker-compose --version)"

# Create app directory
echo "[4/5] Creating application directory..."
APP_DIR="/opt/delta-to-json"
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR

# Create .env template
echo "[5/5] Creating environment file template..."
cat > $APP_DIR/.env.template << 'EOF'
# Database
DB_PASSWORD=your_secure_password_here

# JWT Secret (generate with: openssl rand -hex 32)
JWT_SECRET_KEY=your_jwt_secret_here

# OAuth - Google (optional)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# OAuth - GitHub (optional)
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=

# App URL
APP_URL=http://your-domain-or-ip:8000

# GitHub Container Registry
GITHUB_REPOSITORY=your-username/delta-to-json
EOF

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Copy .env.template to .env and fill in values:"
echo "   cp $APP_DIR/.env.template $APP_DIR/.env"
echo "   nano $APP_DIR/.env"
echo ""
echo "2. Install GitHub Actions self-hosted runner:"
echo "   Go to: https://github.com/YOUR_USERNAME/delta-to-json/settings/actions/runners/new"
echo "   Follow the instructions to install the runner"
echo ""
echo "3. Or run the runner-setup.sh script after setting up the repo"
