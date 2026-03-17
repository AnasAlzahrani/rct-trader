#!/bin/bash
# RCT Trader - Automated Deployment Script
# Run this on your fresh VPS to set up everything automatically

set -e  # Exit on error

echo "=========================================="
echo "  RCT Trader - Cloud Deployment Script"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    print_error "Please run as root (use sudo)"
    exit 1
fi

# Get server IP
SERVER_IP=$(hostname -I | awk '{print $1}')
print_status "Server IP: $SERVER_IP"

# Step 1: Update system
print_status "Step 1/10: Updating system packages..."
apt update && apt upgrade -y

# Step 2: Install essential packages
print_status "Step 2/10: Installing essential packages..."
apt install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    git \
    curl \
    wget \
    sqlite3 \
    redis-server \
    htop \
    nano \
    ufw \
    fail2ban \
    logrotate \
    unattended-upgrades

# Step 3: Setup timezone
print_status "Step 3/10: Setting timezone to America/New_York..."
timedatectl set-timezone America/New_York

# Step 4: Create bot user
print_status "Step 4/10: Creating bot user..."
if id "rctbot" &>/dev/null; then
    print_warning "User 'rctbot' already exists"
else
    useradd -m -s /bin/bash rctbot
    usermod -aG sudo rctbot
    print_status "Created user 'rctbot'"
fi

# Step 5: Setup directories
print_status "Step 5/10: Setting up directories..."
BOT_DIR="/home/rctbot/apps/RCTTrader"
mkdir -p $BOT_DIR
mkdir -p /home/rctbot/backups
chown -R rctbot:rctbot /home/rctbot

# Step 6: Start Redis
print_status "Step 6/10: Starting Redis..."
systemctl enable redis
systemctl start redis
redis-cli ping > /dev/null 2>&1 && print_status "Redis is running" || print_warning "Redis failed to start"

# Step 7: Setup firewall
print_status "Step 7/10: Configuring firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
print_status "Firewall configured"

# Step 8: Setup Fail2Ban
print_status "Step 8/10: Configuring Fail2Ban..."
systemctl enable fail2ban
systemctl start fail2ban

# Step 9: Create systemd service file
print_status "Step 9/10: Creating systemd service..."
cat > /etc/systemd/system/rct-trader.service << 'EOF'
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

StandardOutput=append:/home/rctbot/apps/RCTTrader/logs/system.log
StandardError=append:/home/rctbot/apps/RCTTrader/logs/system.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
print_status "Systemd service created"

# Step 10: Setup log rotation
print_status "Step 10/10: Setting up log rotation..."
cat > /etc/logrotate.d/rct-trader << 'EOF'
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
EOF

# Create backup script
print_status "Creating backup script..."
cat > /home/rctbot/apps/RCTTrader/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/home/rctbot/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Backup database
if [ -f /home/rctbot/apps/RCTTrader/data/rct_trader.db ]; then
    cp /home/rctbot/apps/RCTTrader/data/rct_trader.db $BACKUP_DIR/rct_trader_$DATE.db
    gzip $BACKUP_DIR/rct_trader_$DATE.db
fi

# Keep only last 30 backups
ls -t $BACKUP_DIR/*.db.gz 2>/dev/null | tail -n +31 | xargs -r rm

echo "Backup completed: $DATE"
EOF

chmod +x /home/rctbot/apps/RCTTrader/backup.sh
chown -R rctbot:rctbot /home/rctbot

# Create update script
print_status "Creating update script..."
cat > /home/rctbot/apps/RCTTrader/update.sh << 'EOF'
#!/bin/bash
cd /home/rctbot/apps/RCTTrader

# Pull latest code
if [ -d .git ]; then
    git pull origin main
fi

# Update dependencies
source venv/bin/activate
pip install -r requirements.txt

# Restart service
sudo systemctl restart rct-trader

echo "Updated at $(date)"
EOF

chmod +x /home/rctbot/apps/RCTTrader/update.sh
chown rctbot:rctbot /home/rctbot/apps/RCTTrader/update.sh

# Setup cron jobs for backups
print_status "Setting up cron jobs..."
(crontab -u rctbot -l 2>/dev/null || echo "") | grep -v "backup.sh" | { cat; echo "0 2 * * * /home/rctbot/apps/RCTTrader/backup.sh"; } | crontab -u rctbot -

print_status ""
print_status "=========================================="
print_status "  Deployment Preparation Complete!"
print_status "=========================================="
print_status ""
print_status "Next steps:"
print_status ""
print_status "1. Upload your code to: $BOT_DIR"
print_status "   Option A: git clone your repository"
print_status "   Option B: Use scp to upload files"
print_status ""
print_status "2. Switch to bot user:"
print_status "   su - rctbot"
print_status ""
print_status "3. Create virtual environment:"
print_status "   cd ~/apps/RCTTrader"
print_status "   python3.11 -m venv venv"
print_status "   source venv/bin/activate"
print_status "   pip install -r requirements.txt"
print_status ""
print_status "4. Configure your .env file:"
print_status "   nano ~/apps/RCTTrader/.env"
print_status ""
print_status "5. Start the bot:"
print_status "   sudo systemctl enable rct-trader"
print_status "   sudo systemctl start rct-trader"
print_status ""
print_status "6. Check status:"
print_status "   sudo systemctl status rct-trader"
print_status "   tail -f ~/apps/RCTTrader/logs/rct_trader.log"
print_status ""
print_status "Server IP: $SERVER_IP"
print_status ""
print_status "Useful commands:"
print_status "  - Start:   sudo systemctl start rct-trader"
print_status "  - Stop:    sudo systemctl stop rct-trader"
print_status "  - Restart: sudo systemctl restart rct-trader"
print_status "  - Logs:    sudo journalctl -u rct-trader -f"
print_status ""
