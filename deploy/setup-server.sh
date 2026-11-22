#!/bin/bash
# ResumeIQ Server Setup Script
# Run this ONCE on a fresh Ubuntu 24.04 droplet
# Usage: sudo bash setup-server.sh

set -e

# === CONFIGURATION ===
APP_USER="resumeiq"
APP_DIR="/opt/resumeiq"
DOMAIN="resumeiq.site"

echo "================================================"
echo "ResumeIQ Server Setup - Security Hardened"
echo "================================================"

# === 1. SYSTEM UPDATE ===
echo "[1/8] Updating system..."
apt update && apt upgrade -y
apt install -y curl wget git ufw fail2ban unattended-upgrades

# === 2. CREATE APP USER ===
echo "[2/8] Creating application user..."
if ! id "$APP_USER" &>/dev/null; then
    useradd -m -s /bin/bash "$APP_USER"
    mkdir -p /home/$APP_USER/.ssh
    cp ~/.ssh/authorized_keys /home/$APP_USER/.ssh/ 2>/dev/null || true
    chown -R $APP_USER:$APP_USER /home/$APP_USER/.ssh
    chmod 700 /home/$APP_USER/.ssh
    chmod 600 /home/$APP_USER/.ssh/authorized_keys 2>/dev/null || true
    echo "$APP_USER ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/$APP_USER
fi

# === 3. FIREWALL ===
echo "[3/8] Configuring firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp   # SSH
ufw allow 80/tcp   # HTTP
ufw allow 443/tcp  # HTTPS
ufw --force enable

# === 4. FAIL2BAN ===
echo "[4/8] Configuring Fail2ban..."
systemctl enable fail2ban
systemctl start fail2ban

# === 5. INSTALL PYTHON ===
echo "[5/8] Installing Python 3.11..."
apt install -y python3.11 python3.11-venv python3-pip

# === 6. INSTALL NODE.JS ===
echo "[6/8] Installing Node.js 20..."
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs

# === 7. INSTALL NGINX ===
echo "[7/8] Installing Nginx..."
apt install -y nginx
systemctl enable nginx

# === 8. INSTALL CERTBOT ===
echo "[8/8] Installing Certbot for SSL..."
apt install -y certbot python3-certbot-nginx

# === CREATE APP DIRECTORY ===
mkdir -p $APP_DIR
chown $APP_USER:$APP_USER $APP_DIR

# === SECURE SSH (disable password auth) ===
echo "Securing SSH..."
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl reload sshd

# === AUTO SECURITY UPDATES ===
echo "Enabling automatic security updates..."
dpkg-reconfigure -plow unattended-upgrades

echo ""
echo "================================================"
echo "✅ Server setup complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo "1. Copy your app files to: $APP_DIR"
echo "2. Run: sudo bash deploy.sh"
echo "3. Set up SSL: sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN"
echo ""
echo "SSH as app user: ssh $APP_USER@<your-ip>"
