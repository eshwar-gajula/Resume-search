#!/bin/bash
# ResumeIQ Deployment Script
# Run this to deploy/update the application
# Usage: sudo bash deploy.sh

set -e

# === CONFIGURATION ===
APP_USER="resumeiq"
APP_DIR="/opt/resumeiq"
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIR="$APP_DIR/frontend"

echo "================================================"
echo "ResumeIQ Deployment"
echo "================================================"

# === CHECK IF RUNNING AS ROOT ===
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo bash deploy.sh)"
    exit 1
fi

# === 1. BACKEND SETUP ===
echo "[1/5] Setting up backend..."
cd $BACKEND_DIR

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    python3.11 -m venv venv
fi

# Install dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# Create uploads directory
mkdir -p uploads
chown -R $APP_USER:$APP_USER $BACKEND_DIR

# === 2. FRONTEND SETUP ===
echo "[2/5] Setting up frontend..."
cd $FRONTEND_DIR

npm install
NEXT_PUBLIC_API_URL="https://resumeiq.site/api" npm run build
chown -R $APP_USER:$APP_USER $FRONTEND_DIR

# === 3. INSTALL SYSTEMD SERVICES ===
echo "[3/5] Installing systemd services..."
cp $APP_DIR/deploy/resumeiq-backend.service /etc/systemd/system/
cp $APP_DIR/deploy/resumeiq-frontend.service /etc/systemd/system/
systemctl daemon-reload

# === 4. CONFIGURE NGINX ===
echo "[4/5] Configuring Nginx..."
cp $APP_DIR/deploy/nginx.conf /etc/nginx/sites-available/resumeiq
ln -sf /etc/nginx/sites-available/resumeiq /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# === 5. START SERVICES ===
echo "[5/5] Starting services..."
systemctl enable resumeiq-backend resumeiq-frontend
systemctl restart resumeiq-backend resumeiq-frontend

echo ""
echo "================================================"
echo "✅ Deployment complete!"
echo "================================================"
echo ""
echo "Services status:"
systemctl status resumeiq-backend --no-pager -l || true
systemctl status resumeiq-frontend --no-pager -l || true
echo ""
echo "View logs: journalctl -u resumeiq-backend -f"
