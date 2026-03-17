# RCT Trader - Cloud Deployment Guide

Deploy your trading bot to run 24/7 on a cloud VPS (Virtual Private Server).

## Table of Contents
1. [Choose a Cloud Provider](#1-choose-a-cloud-provider)
2. [Create Your VPS](#2-create-your-vps)
3. [Connect to Your Server](#3-connect-to-your-server)
4. [Install Dependencies](#4-install-dependencies)
5. [Deploy the Bot](#5-deploy-the-bot)
6. [Run 24/7 as a Service](#6-run-247-as-a-service)
7. [Monitor & Maintain](#7-monitor--maintain)
8. [Security Setup](#8-security-setup)

---

## 1. Choose a Cloud Provider

### Recommended Options (Cheapest to Best)

| Provider | Cost/Month | Specs | Best For |
|----------|------------|-------|----------|
| **Vultr** | $5-10 | 1GB RAM, 1 CPU | Budget, beginners |
| **DigitalOcean** | $6-12 | 1GB RAM, 1 CPU | Easy setup, tutorials |
| **Linode** | $5-10 | 1GB RAM, 1 CPU | Reliable, good support |
| **AWS Lightsail** | $5-10 | 1GB RAM, 1 CPU | AWS ecosystem |
| **Hetzner** | €4-8 | 2GB RAM, 1 CPU | Best value (Europe) |
| **Oracle Cloud** | **FREE** | 1GB RAM, 1 CPU | Free tier available |

### Our Recommendation: **DigitalOcean** or **Vultr**
- Simplest setup
- Good documentation
- $5/month is enough for this bot

---

## 2. Create Your VPS

### Option A: DigitalOcean (Recommended for Beginners)

#### Step 2.1: Create Account
1. Go to [DigitalOcean](https://www.digitalocean.com/)
2. Sign up with email or GitHub
3. Add payment method (credit card or PayPal)
4. You might get $200 free credit!

#### Step 2.2: Create Droplet (VPS)
1. Click **"Create"** → **"Droplets"**
2. Choose Region: Pick closest to you (e.g., New York, London, Singapore)
3. Choose Image: **Ubuntu 22.04 (LTS) x64**
4. Choose Plan:
   - **Basic**
   - **$6/month** (1 GB RAM / 1 CPU / 25 GB SSD)
   - This is enough for the bot
5. Choose Authentication:
   - Select **"Password"** (easier for beginners)
   - Or **"SSH Key"** (more secure)
6. Quantity: 1
7. Hostname: `rct-trader-bot`
8. Click **"Create Droplet"**

#### Step 2.3: Get Your IP Address
- Wait 1 minute for creation
- You'll see your droplet with an IP address like: `192.168.1.100`
- **Save this IP!**

---

### Option B: Vultr (Cheaper)

#### Step 2.1: Create Account
1. Go to [Vultr](https://www.vultr.com/)
2. Sign up and add payment method

#### Step 2.2: Deploy Server
1. Click **"Deploy"** → **"Deploy New Server"**
2. Choose Server: **Cloud Compute**
3. Location: Pick closest to you
4. Server Type: **Ubuntu 22.04 LTS**
5. Server Size: **$5/month** (1 CPU, 1GB RAM, 25GB SSD)
6. Add SSH Keys: (optional, can add password)
7. Server Hostname: `rct-trader`
8. Click **"Deploy Now"**

---

### Option C: Oracle Cloud (FREE!)

#### Step 2.1: Create Account
1. Go to [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/)
2. Sign up (requires credit card for verification, but won't be charged)
3. You'll get **Always Free** resources

#### Step 2.2: Create Instance
1. Go to **Compute** → **Instances**
2. Click **"Create Instance"**
3. Name: `rct-trader`
4. Image: **Canonical Ubuntu 22.04**
5. Shape: **VM.Standard.E2.1.Micro** (Always Free)
6. Add SSH keys
7. Click **"Create"**

---

## 3. Connect to Your Server

### Step 3.1: Open Terminal

**Windows:**
- Download [PuTTY](https://www.putty.org/) OR
- Use Windows Terminal / PowerShell

**Mac/Linux:**
- Open Terminal app

### Step 3.2: Connect via SSH

Using password (DigitalOcean/Vultr):
```bash
ssh root@YOUR_SERVER_IP
```

Example:
```bash
ssh root@192.168.1.100
```

You'll be asked for password (from email or dashboard).

### Step 3.3: First Time Setup

Once connected, update the system:
```bash
apt update && apt upgrade -y
```

Set your timezone:
```bash
timedatectl set-timezone America/New_York  # Change to your timezone
```

List of timezones:
```bash
timedatectl list-timezones | grep -i "new_york"
```

---

## 4. Install Dependencies

### Step 4.1: Install Python & Git

```bash
# Install Python 3.11 and other essentials
apt install -y python3.11 python3.11-venv python3-pip git curl wget

# Verify installation
python3.11 --version  # Should show Python 3.11.x
git --version
```

### Step 4.2: Install SQLite (Database)

```bash
apt install -y sqlite3
```

### Step 4.3: Install Redis (Optional - for caching)

```bash
apt install -y redis-server

# Start Redis
systemctl enable redis
systemctl start redis

# Test Redis
redis-cli ping  # Should return "PONG"
```

---

## 5. Deploy the Bot

### Step 5.1: Create Bot User (Security Best Practice)

```bash
# Create a new user for the bot
useradd -m -s /bin/bash rctbot

# Add to sudoers
usermod -aG sudo rctbot

# Switch to bot user
su - rctbot
```

### Step 5.2: Clone the Repository

```bash
# Create directory
mkdir -p ~/apps
cd ~/apps

# Clone your repository (replace with your actual repo)
git clone https://github.com/yourusername/RCTTrader.git
cd RCTTrader
```

If you don't have a GitHub repo yet, upload files via SCP (see Step 5.2b).

### Step 5.2b: Upload Files via SCP (Alternative)

From your local computer:
```bash
# Zip your project
cd /path/to/RCTTrader
zip -r rct-trader.zip .

# Upload to server (from your local terminal)
scp rct-trader.zip root@YOUR_SERVER_IP:/home/rctbot/apps/
```

On server:
```bash
su - rctbot
cd ~/apps
unzip rct-trader.zip -d RCTTrader
cd RCTTrader
```

### Step 5.3: Create Virtual Environment

```bash
# Create virtual environment
python3.11 -m venv venv

# Activate it
source venv/bin/activate

# You should see (venv) in your prompt
```

### Step 5.4: Install Python Dependencies

```bash
# Install requirements
pip install --upgrade pip
pip install -r requirements.txt

# This will take 2-5 minutes
```

### Step 5.5: Create Environment File

```bash
# Copy example
nano .env
```

Paste your configuration:
```env
# App Settings
DEBUG=false
LOG_LEVEL=INFO

# Trading Settings
TRADING_MODE=alert
RISK_PROFILE=moderate
INITIAL_CAPITAL=100000

# Signal Thresholds
MIN_CONFIDENCE=0.55
STRONG_BUY_THRESHOLD=0.75
BUY_THRESHOLD=0.60

# Risk Management
MAX_POSITION_SIZE_PCT=0.05
MAX_DAILY_LOSS_PCT=0.03

# Database
DATABASE_URL=sqlite+aiosqlite:///data/rct_trader.db

# Alerts - ADD YOUR CREDENTIALS!
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_IDS=your_chat_id

EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_app_password

# Alpaca (for paper/live trading later)
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_PAPER=true
```

Save: `Ctrl+O`, then `Enter`, then `Ctrl+X`

### Step 5.6: Create Required Directories

```bash
mkdir -p data logs
```

### Step 5.7: Test the Bot

```bash
# Run demo to test
python -m src.bot demo
```

If you see output, it's working!

---

## 6. Run 24/7 as a Service

### Step 6.1: Create Systemd Service

Create service file:
```bash
sudo nano /etc/systemd/system/rct-trader.service
```

Paste this:
```ini
[Unit]
Description=RCT Trader Bot
After=network.target redis.service

[Service]
Type=simple
User=rctbot
Group=rctbot
WorkingDirectory=/home/rctbot/apps/RCTTrader
Environment=PATH=/home/rctbot/apps/RCTTrader/venv/bin
ExecStart=/home/rctbot/apps/RCTTrader/venv/bin/python -m src.bot run
Restart=always
RestartSec=10

# Logging
StandardOutput=append:/home/rctbot/apps/RCTTrader/logs/system.log
StandardError=append:/home/rctbot/apps/RCTTrader/logs/system.log

[Install]
WantedBy=multi-user.target
```

Save and exit.

### Step 6.2: Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable rct-trader

# Start the service
sudo systemctl start rct-trader

# Check status
sudo systemctl status rct-trader
```

### Step 6.3: Manage the Service

```bash
# Start
sudo systemctl start rct-trader

# Stop
sudo systemctl stop rct-trader

# Restart
sudo systemctl restart rct-trader

# View logs
sudo journalctl -u rct-trader -f

# View recent logs
sudo journalctl -u rct-trader --since "1 hour ago"
```

---

## 7. Monitor & Maintain

### Step 7.1: View Bot Logs

```bash
# Application logs
tail -f ~/apps/RCTTrader/logs/rct_trader.log

# System service logs
sudo journalctl -u rct-trader -f
```

### Step 7.2: Check Bot Status

```bash
# Is the service running?
sudo systemctl is-active rct-trader

# Full status
sudo systemctl status rct-trader
```

### Step 7.3: Monitor Resources

```bash
# CPU and memory usage
htop

# Or use top
top -p $(pgrep -f "src.bot")

# Disk usage
df -h

# Memory usage
free -h
```

### Step 7.4: Setup Log Rotation (Important!)

Prevent logs from filling up disk:
```bash
sudo nano /etc/logrotate.d/rct-trader
```

Paste:
```
/home/rctbot/apps/RCTTrader/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0644 rctbot rctbot
    sharedscripts
    postrotate
        systemctl reload rct-trader
    endscript
}
```

### Step 7.5: Setup Automated Updates (Optional)

Create update script:
```bash
nano ~/apps/RCTTrader/update.sh
```

Paste:
```bash
#!/bin/bash
cd /home/rctbot/apps/RCTTrader
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart rct-trader
echo "Updated at $(date)"
```

Make executable:
```bash
chmod +x ~/apps/RCTTrader/update.sh
```

---

## 8. Security Setup

### Step 8.1: Configure Firewall

```bash
# Install UFW (Uncomplicated Firewall)
sudo apt install -y ufw

# Default deny incoming
sudo ufw default deny incoming

# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS (for future web dashboard)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

### Step 8.2: Disable Root Login (Recommended)

```bash
# Edit SSH config
sudo nano /etc/ssh/sshd_config
```

Find and modify:
```
PermitRootLogin no
PasswordAuthentication no  # Only if using SSH keys
```

Restart SSH:
```bash
sudo systemctl restart sshd
```

### Step 8.3: Setup Automatic Security Updates

```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure unattended-upgrades
# Select "Yes"
```

### Step 8.4: Install Fail2Ban (Blocks Hackers)

```bash
sudo apt install -y fail2ban

# Start service
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

---

## 9. Backup Your Data

### Step 9.1: Database Backup Script

```bash
nano ~/apps/RCTTrader/backup.sh
```

Paste:
```bash
#!/bin/bash
BACKUP_DIR="/home/rctbot/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Backup database
cp /home/rctbot/apps/RCTTrader/data/rct_trader.db $BACKUP_DIR/rct_trader_$DATE.db

# Keep only last 30 backups
ls -t $BACKUP_DIR/*.db | tail -n +31 | xargs -r rm

echo "Backup completed: $DATE"
```

Make executable:
```bash
chmod +x ~/apps/RCTTrader/backup.sh
```

### Step 9.2: Schedule Daily Backups

```bash
crontab -e
```

Add:
```
0 2 * * * /home/rctbot/apps/RCTTrader/backup.sh
```

This runs at 2 AM daily.

---

## 10. Troubleshooting

### Problem: Bot won't start

```bash
# Check logs
sudo journalctl -u rct-trader -n 50

# Check Python errors
tail -f ~/apps/RCTTrader/logs/rct_trader.log

# Test manually
cd ~/apps/RCTTrader
source venv/bin/activate
python -m src.bot scan
```

### Problem: Out of memory

```bash
# Check memory
free -h

# Add swap space
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Problem: Disk full

```bash
# Check disk usage
df -h

# Find large files
sudo du -h / | grep '^[0-9\.]*G'

# Clear old logs
sudo journalctl --vacuum-time=7d
```

### Problem: Service keeps restarting

```bash
# Check for errors
sudo journalctl -u rct-trader -n 100 | grep -i error

# Check if port is in use
sudo lsof -i :8000

# Check file permissions
ls -la ~/apps/RCTTrader/
```

---

## 11. Cost Optimization

### Reduce Costs

| Tip | Savings |
|-----|---------|
| Use Oracle Cloud Free Tier | $0/month |
| Use Hetzner (Europe) | ~50% cheaper |
| Shutdown during market close | ~60% savings |
| Use spot instances (AWS) | ~70% savings |

### Auto-Shutdown (Optional)

If you only trade during market hours:

```bash
# Edit crontab
crontab -e
```

```
# Stop bot at 8 PM ET (weekdays)
0 20 * * 1-5 sudo systemctl stop rct-trader

# Start bot at 8 AM ET (weekdays)
0 8 * * 1-5 sudo systemctl start rct-trader
```

---

## Quick Reference Commands

```bash
# Connect to server
ssh root@YOUR_SERVER_IP

# Check bot status
sudo systemctl status rct-trader

# View logs
tail -f ~/apps/RCTTrader/logs/rct_trader.log

# Restart bot
sudo systemctl restart rct-trader

# Update bot
cd ~/apps/RCTTrader && git pull && sudo systemctl restart rct-trader

# Check resources
htop

# Check disk space
df -h
```

---

## Next Steps

1. **Setup Monitoring**: Add UptimeRobot or Pingdom to alert if bot goes down
2. **Web Dashboard**: Deploy React frontend (see dashboard/ folder)
3. **Alpaca Integration**: Configure paper trading
4. **Alerts**: Configure Telegram/Discord for signal notifications

---

**Your bot is now running 24/7 in the cloud!** 🚀

Need help? Check logs with: `sudo journalctl -u rct-trader -f`
