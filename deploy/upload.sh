#!/bin/bash
# Upload project to server (run from Windows WSL or Git Bash)
# Usage: bash upload.sh <server-ip>

set -e

SERVER_IP=${1:-"your-server-ip"}
REMOTE_USER="resumeiq"
REMOTE_DIR="/opt/resumeiq"

echo "Uploading to $REMOTE_USER@$SERVER_IP:$REMOTE_DIR"

# Upload backend (excluding venv, __pycache__)
rsync -avz --progress \
    --exclude 'venv' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.env' \
    --exclude 'uploads/*' \
    --exclude '*.db' \
    ../backend/ $REMOTE_USER@$SERVER_IP:$REMOTE_DIR/backend/

# Upload frontend (excluding node_modules, .next)
rsync -avz --progress \
    --exclude 'node_modules' \
    --exclude '.next' \
    ../frontend/ $REMOTE_USER@$SERVER_IP:$REMOTE_DIR/frontend/

# Upload deploy scripts
rsync -avz --progress \
    ./ $REMOTE_USER@$SERVER_IP:$REMOTE_DIR/deploy/

echo ""
echo "✅ Upload complete!"
echo ""
echo "Now SSH to server and run:"
echo "  sudo bash /opt/resumeiq/deploy/deploy.sh"
