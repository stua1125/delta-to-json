#!/bin/bash
# Manual Deployment Script
# Run this on the target server for manual deployments

set -e

APP_DIR="/opt/delta-to-json"
REPO_URL="https://github.com/YOUR_USERNAME/delta-to-json.git"  # Update this

echo "=== Delta-to-JSON Deployment ==="

cd $APP_DIR

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    echo "Please create .env from .env.template first"
    exit 1
fi

# Load environment variables
export $(grep -v '^#' .env | xargs)

# Pull latest code (if git repo exists)
if [ -d ".git" ]; then
    echo "[1/4] Pulling latest code..."
    git pull origin main
else
    echo "[1/4] Cloning repository..."
    cd /opt
    git clone $REPO_URL delta-to-json-tmp
    cp delta-to-json/.env delta-to-json-tmp/
    rm -rf delta-to-json
    mv delta-to-json-tmp delta-to-json
    cd $APP_DIR
fi

# Copy production compose file
cp docker-compose.prod.yml docker-compose.yml 2>/dev/null || true

# Pull and deploy
echo "[2/4] Pulling latest images..."
docker-compose pull 2>/dev/null || docker compose pull

echo "[3/4] Deploying..."
docker-compose up -d --remove-orphans 2>/dev/null || docker compose up -d --remove-orphans

echo "[4/4] Running database migrations..."
sleep 5
docker-compose exec -T app alembic upgrade head 2>/dev/null || \
    docker compose exec -T app alembic upgrade head 2>/dev/null || \
    echo "Migration skipped (tables may already exist)"

echo ""
echo "=== Deployment Complete ==="
docker-compose ps 2>/dev/null || docker compose ps

echo ""
echo "Health check:"
curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || echo "Waiting for service to start..."
