# ResumeIQ Deployment Guide

Deploy to DigitalOcean Droplet ($6/mo, 1GB RAM).

---

## Quick Start

### 1. Create Droplet
- Ubuntu 24.04 LTS
- 1GB RAM / 1 vCPU ($6/mo)
- Add your SSH key

### 2. Point DNS
In your domain registrar, add:
```
A    @      → <droplet-ip>
A    www    → <droplet-ip>
```

### 3. Initial Server Setup
```bash
ssh root@<droplet-ip>
mkdir -p /opt/resumeiq
```

### 4. Upload Code (from your local machine)
```bash
cd deploy
bash upload.sh <droplet-ip>
```

### 5. Run Server Setup (first time only)
```bash
ssh root@<droplet-ip>
bash /opt/resumeiq/deploy/setup-server.sh
```

### 6. Configure Production Environment
```bash
ssh resumeiq@<droplet-ip>
cd /opt/resumeiq/backend
cp .env.production.example .env
nano .env  # Fill in real values
```

**Important:** Generate a strong JWT secret:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 7. Deploy Application
```bash
sudo bash /opt/resumeiq/deploy/deploy.sh
```

### 8. Setup SSL
```bash
sudo certbot --nginx -d resumeiq.site -d www.resumeiq.site
```

---

## Updating the App

After making changes locally:
```bash
# From deploy/ folder
bash upload.sh <droplet-ip>

# Then on server
ssh resumeiq@<droplet-ip>
sudo bash /opt/resumeiq/deploy/deploy.sh
```

---

## Useful Commands

```bash
# View logs
journalctl -u resumeiq-backend -f
journalctl -u resumeiq-frontend -f

# Restart services
sudo systemctl restart resumeiq-backend
sudo systemctl restart resumeiq-frontend

# Check status
sudo systemctl status resumeiq-backend
sudo systemctl status resumeiq-frontend
```

---

## Security Checklist

- [x] UFW firewall (22, 80, 443 only)
- [x] Fail2ban enabled
- [x] SSH key-only (password disabled)
- [x] Security headers in Nginx
- [x] HTTPS with Let's Encrypt
- [ ] Rate limiting on API (TODO)
- [ ] Strong JWT_SECRET set
- [ ] CORS_ORIGINS set to https://resumeiq.site
