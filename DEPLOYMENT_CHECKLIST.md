# Deployment Checklist - RCT Trader 24/7 Cloud Setup

Use this checklist to deploy your bot to the cloud.

---

## Pre-Deployment

- [ ] **Choose Cloud Provider**
  - [ ] DigitalOcean ($6/month) - Easiest ⭐
  - [ ] Oracle Cloud ($0/month) - Free but complex
  - [ ] Vultr ($5/month) - Cheapest
  - [ ] Hetzner (~$5/month) - Best value

- [ ] **Create Account**
  - [ ] Sign up on provider website
  - [ ] Add payment method
  - [ ] Claim any free credits

- [ ] **Prepare Your Code**
  - [ ] Make sure all files are in RCTTrader folder
  - [ ] Update `.env` with your API keys
  - [ ] Test locally: `python -m src.bot demo`

---

## Step 1: Create VPS (5 min)

- [ ] **DigitalOcean**
  - [ ] Click "Create" → "Droplets"
  - [ ] Select Ubuntu 22.04 LTS
  - [ ] Choose $6/month (1GB RAM)
  - [ ] Set password or SSH key
  - [ ] Click "Create Droplet"
  - [ ] **Save IP address!**

- [ ] **Oracle Cloud (Free)**
  - [ ] Go to Compute → Instances
  - [ ] Click "Create Instance"
  - [ ] Select Ubuntu 22.04
  - [ ] Choose "Always Free" shape
  - [ ] Add SSH key
  - [ ] Click "Create"

---

## Step 2: Connect to Server (2 min)

- [ ] **Get Server IP** (from dashboard)
- [ ] **Connect via SSH**
  - Mac/Linux: `ssh root@YOUR_IP`
  - Windows: Use PuTTY
- [ ] **Enter password** when prompted

---

## Step 3: Run Setup Script (5 min)

- [ ] **Download and run auto-setup**
  ```bash
  curl -fsSL https://your-domain.com/deploy.sh | sudo bash
  ```
  
  OR manually:
  
  ```bash
  # Update system
  apt update && apt upgrade -y
  
  # Install dependencies
  apt install -y python3.11 python3.11-venv python3-pip git redis-server
  
  # Create bot user
  useradd -m -s /bin/bash rctbot
  usermod -aG sudo rctbot
  
  # Create directories
  mkdir -p /home/rctbot/apps/RCTTrader
  ```

---

## Step 4: Upload Your Code (2 min)

- [ ] **From your local computer:**
  ```bash
  # Zip the project
  cd /path/to/RCTTrader
  zip -r rct-trader.zip .
  
  # Upload to server
  scp rct-trader.zip root@YOUR_IP:/home/rctbot/apps/
  ```

- [ ] **On server:**
  ```bash
  cd /home/rctbot/apps
  unzip rct-trader.zip -d RCTTrader
  chown -R rctbot:rctbot /home/rctbot
  ```

---

## Step 5: Install & Configure (3 min)

- [ ] **Switch to bot user**
  ```bash
  su - rctbot
  ```

- [ ] **Setup Python environment**
  ```bash
  cd ~/apps/RCTTrader
  python3.11 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```

- [ ] **Create directories**
  ```bash
  mkdir -p data logs
  ```

- [ ] **Configure environment**
  ```bash
  nano .env
  ```
  
  Minimum config:
  ```env
  TRADING_MODE=alert
  TELEGRAM_BOT_TOKEN=your_token_here
  TELEGRAM_CHAT_IDS=your_chat_id
  ```
  
  Save: `Ctrl+O`, `Enter`, `Ctrl+X`

---

## Step 6: Test the Bot (2 min)

- [ ] **Run demo**
  ```bash
  python -m src.bot demo
  ```
  
- [ ] **Verify output**
  - [ ] See signal table
  - [ ] No errors
  - [ ] Rich formatting works

---

## Step 7: Start 24/7 Service (1 min)

- [ ] **Exit bot user shell**
  ```bash
  exit
  ```

- [ ] **Enable and start service**
  ```bash
  systemctl enable rct-trader
  systemctl start rct-trader
  ```

- [ ] **Verify it's running**
  ```bash
  systemctl status rct-trader
  ```
  
  Should show: "active (running)"

---

## Step 8: Verify & Monitor (2 min)

- [ ] **Check logs**
  ```bash
  # Application logs
  tail -f /home/rctbot/apps/RCTTrader/logs/rct_trader.log
  
  # System logs
  journalctl -u rct-trader -f
  ```

- [ ] **Run health check**
  ```bash
  bash /home/rctbot/apps/RCTTrader/health_check.sh
  ```

- [ ] **Check resource usage**
  ```bash
  htop
  ```

---

## Post-Deployment

- [ ] **Setup monitoring**
  - [ ] Add UptimeRobot or Pingdom
  - [ ] Configure alerts

- [ ] **Configure alerts**
  - [ ] Telegram bot working
  - [ ] Email alerts (optional)
  - [ ] Test notifications

- [ ] **Security**
  - [ ] Firewall enabled: `ufw status`
  - [ ] Fail2Ban running: `systemctl status fail2ban`
  - [ ] (Optional) Disable root login

- [ ] **Backups**
  - [ ] Backup script created
  - [ ] Cron job scheduled
  - [ ] Test restore process

---

## Daily Operations

### Check Bot Status
```bash
# Quick status check
systemctl is-active rct-trader

# Full status
systemctl status rct-trader

# Health check
bash /home/rctbot/apps/RCTTrader/health_check.sh
```

### View Logs
```bash
# Real-time logs
journalctl -u rct-trader -f

# Last 100 lines
journalctl -u rct-trader -n 100

# Today's logs
journalctl -u rct-trader --since today

# Application logs
tail -f /home/rctbot/apps/RCTTrader/logs/rct_trader.log
```

### Manage Bot
```bash
# Start
systemctl start rct-trader

# Stop
systemctl stop rct-trader

# Restart
systemctl restart rct-trader

# View recent errors
journalctl -u rct-trader -p err -n 20
```

### Update Bot
```bash
# Run update script
su - rctbot
bash /home/rctbot/apps/RCTTrader/update.sh
```

---

## Troubleshooting

### Bot won't start
```bash
# Check logs
journalctl -u rct-trader -n 50

# Test manually
su - rctbot
cd ~/apps/RCTTrader
source venv/bin/activate
python -m src.bot demo
```

### Out of memory
```bash
# Add swap
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

### Disk full
```bash
# Check usage
df -h

# Clean old logs
journalctl --vacuum-time=7d

# Clean compressed logs
find /home/rctbot/apps/RCTTrader/logs -name "*.gz" -mtime +7 -delete
```

### Can't connect
```bash
# Check SSH service
systemctl status ssh

# Check firewall
ufw status

# Check if server is up
ping YOUR_SERVER_IP
```

---

## Monthly Maintenance

- [ ] **Check disk space** (`df -h`)
- [ ] **Review logs** for errors
- [ ] **Update system** (`apt update && apt upgrade`)
- [ ] **Backup database**
- [ ] **Review bot performance**
- [ ] **Check costs** (cloud provider billing)

---

## Emergency Contacts

| Issue | Command |
|-------|---------|
| Bot stuck | `systemctl restart rct-trader` |
| High CPU | `htop` then `kill -9 PID` |
| Disk full | `rm -rf /home/rctbot/apps/RCTTrader/logs/*.gz` |
| Forgot password | Reset via cloud provider console |
| Server unreachable | Reboot via cloud provider console |

---

## Cost Tracking

| Month | Provider | Cost | Notes |
|-------|----------|------|-------|
| Jan | DigitalOcean | $6 | First month |
| Feb | DigitalOcean | $6 | - |
| Mar | ? | ? | - |

---

## Quick Reference Card

```
╔══════════════════════════════════════════════╗
║         RCT Trader - Quick Commands          ║
╠══════════════════════════════════════════════╣
║ Connect:    ssh root@YOUR_IP                 ║
║ Status:     systemctl status rct-trader      ║
║ Start:      systemctl start rct-trader       ║
║ Stop:       systemctl stop rct-trader        ║
║ Restart:    systemctl restart rct-trader     ║
║ Logs:       journalctl -u rct-trader -f      ║
║ Health:     bash health_check.sh             ║
║ Resources:  htop                             ║
╚══════════════════════════════════════════════╝
```

---

## You're Done! 🎉

Your bot is now running 24/7 in the cloud!

**What's Next?**
1. Monitor signals in Telegram/Email
2. Review performance weekly
3. Consider paper trading when confident
4. Upgrade server if needed (2GB RAM)

**Need Help?**
- Check logs: `journalctl -u rct-trader -f`
- Read: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- Health check: `bash health_check.sh`
