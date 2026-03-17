# Quick Deploy - RCT Trader to DigitalOcean

Get your bot running 24/7 in **15 minutes**.

---

## Step 1: Create VPS (5 minutes)

1. Go to [DigitalOcean](https://www.digitalocean.com/) → Sign up
2. Click **"Create"** → **"Droplets"**
3. Choose:
   - **Region**: Closest to you
   - **Image**: Ubuntu 22.04 (LTS)
   - **Plan**: Basic → **$6/month** (1 GB RAM)
   - **Auth**: Password (choose a strong one)
4. Click **"Create Droplet"**
5. **Save the IP address** shown (e.g., `192.168.1.100`)

---

## Step 2: Connect to Server (2 minutes)

**Mac/Linux:**
```bash
ssh root@YOUR_IP_ADDRESS
```

**Windows:**
1. Download [PuTTY](https://www.putty.org/)
2. Enter IP, click Open
3. Login: `root`, enter password

---

## Step 3: Run Auto-Setup (5 minutes)

Copy and paste this entire block:

```bash
# Download and run deployment script
curl -fsSL https://raw.githubusercontent.com/yourusername/RCTTrader/main/deploy.sh | sudo bash
```

Or manually:
```bash
# 1. Update system
apt update && apt upgrade -y

# 2. Install Python & essentials  
apt install -y python3.11 python3.11-venv python3-pip git redis-server

# 3. Create bot user
useradd -m -s /bin/bash rctbot
usermod -aG sudo rctbot

# 4. Setup directories
mkdir -p /home/rctbot/apps/RCTTrader
cd /home/rctbot/apps/RCTTrader

# 5. Upload your files (from your local computer)
# See Step 4 below
```

---

## Step 4: Upload Your Code (2 minutes)

**From your local computer** (new terminal window):

```bash
# Zip your project
cd /path/to/RCTTrader
zip -r rct-trader.zip .

# Upload to server
scp rct-trader.zip root@YOUR_IP_ADDRESS:/home/rctbot/apps/
```

**Back on server**:
```bash
cd /home/rctbot/apps
unzip rct-trader.zip -d RCTTrader
chown -R rctbot:rctbot /home/rctbot
```

---

## Step 5: Install & Configure (3 minutes)

```bash
# Switch to bot user
su - rctbot

# Setup Python environment
cd ~/apps/RCTTrader
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create directories
mkdir -p data logs

# Edit config
nano .env
```

Paste your config (minimum):
```env
TRADING_MODE=alert
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_IDS=your_chat_id
```

Save: `Ctrl+O`, `Enter`, `Ctrl+X`

---

## Step 6: Start the Bot (1 minute)

```bash
# Exit bot user shell
exit

# Start service (as root)
systemctl enable rct-trader
systemctl start rct-trader

# Check it's running
systemctl status rct-trader
```

---

## Done! 🎉

Your bot is now running 24/7!

### Check Logs
```bash
# Application logs
tail -f /home/rctbot/apps/RCTTrader/logs/rct_trader.log

# System logs
journalctl -u rct-trader -f
```

### Manage Bot
```bash
# Start
systemctl start rct-trader

# Stop
systemctl stop rct-trader

# Restart
systemctl restart rct-trader

# Check status
systemctl status rct-trader
```

---

## Troubleshooting

### Bot won't start?
```bash
# Check what's wrong
journalctl -u rct-trader -n 50

# Test manually
su - rctbot
cd ~/apps/RCTTrader
source venv/bin/activate
python -m src.bot demo
```

### Out of memory?
```bash
# Add 2GB swap
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

### Can't connect via SSH?
- Check IP is correct
- Check firewall isn't blocking port 22
- Try: `ssh -v root@YOUR_IP`

---

## Monthly Cost

| Provider | Cost |
|----------|------|
| DigitalOcean | $6/month |
| Vultr | $5/month |
| Linode | $5/month |
| Oracle Cloud | **FREE** |

---

## Need Help?

1. Check logs: `journalctl -u rct-trader -f`
2. Check resources: `htop`
3. Re-read: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
