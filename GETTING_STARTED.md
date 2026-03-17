# Getting Started with RCT Trader

Complete guide to get your trading bot running locally and in the cloud.

---

## What You Have

You now have a **production-ready clinical trials trading bot** with:

| Component | Details |
|-----------|---------|
| **Code** | 3,474 lines of Python |
| **Companies** | 200+ pharma/biotech mappings |
| **Architecture** | Async, modular, enterprise-grade |
| **Alerts** | Console, Email, Telegram, Discord |
| **Database** | 9 tables with full ORM |
| **Documentation** | 7 comprehensive guides |

---

## Quick Start (Local - 5 minutes)

### 1. Install Dependencies
```bash
cd RCTTrader
pip install -r requirements.txt
```

### 2. Configure
```bash
cp .env.example .env
nano .env  # Add your Telegram token
```

### 3. Run Demo
```bash
python -m src.bot demo
```

---

## Deploy to Cloud (24/7) - 15 minutes

### Choose Provider

| Provider | Cost | Best For |
|----------|------|----------|
| **DigitalOcean** | $6/mo | Beginners ⭐ |
| **Oracle Cloud** | **FREE** | No budget |
| **Vultr** | $5/mo | Cheapest |

### Step-by-Step

1. **Create VPS** (5 min)
   - Sign up at [DigitalOcean](https://digitalocean.com)
   - Create Ubuntu 22.04 droplet ($6/month)
   - Save IP address

2. **Connect & Setup** (5 min)
   ```bash
   ssh root@YOUR_IP
   curl -fsSL https://raw.githubusercontent.com/yourname/RCTTrader/main/deploy.sh | sudo bash
   ```

3. **Upload Code** (2 min)
   ```bash
   # From your computer
   scp -r RCTTrader root@YOUR_IP:/home/rctbot/apps/
   ```

4. **Configure & Start** (3 min)
   ```bash
   su - rctbot
cd ~/apps/RCTTrader
   source venv/bin/activate
   nano .env  # Add your tokens
   exit
   systemctl enable rct-trader
   systemctl start rct-trader
   ```

**Done!** Your bot is now running 24/7.

---

## File Guide

### Code Files
| File | Purpose |
|------|---------|
| `src/bot.py` | Main orchestrator |
| `src/data_sources/clinical_trials.py` | CT.gov API client |
| `src/data_sources/company_mapper.py` | 200+ company mappings |
| `src/data_sources/market_data.py` | Yahoo Finance client |
| `src/analysis/signal_generator.py` | Signal scoring |
| `src/analysis/event_study.py` | Statistical analysis |
| `src/alerts/notifier.py` | Multi-channel alerts |
| `src/database/models.py` | Database schema |
| `src/utils/config.py` | Settings management |

### Documentation
| File | Purpose |
|------|---------|
| `README.md` | Main documentation |
| `QUICK_DEPLOY.md` | 15-minute deployment |
| `DEPLOYMENT_GUIDE.md` | Complete deployment |
| `DEPLOYMENT_CHECKLIST.md` | Step-by-step checklist |
| `CLOUD_PROVIDERS.md` | Provider comparison |
| `IMPROVEMENTS.md` | What's improved |
| `PROJECT_SUMMARY.md` | Project overview |

### Scripts
| File | Purpose |
|------|---------|
| `deploy.sh` | Auto-setup script |
| `health_check.sh` | Monitor bot health |

---

## Commands Reference

### Local Development
```bash
# Run demo
python -m src.bot demo

# Scan for trials
python -m src.bot scan --hours 24

# Run continuously
python -m src.bot run

# Run backtest
python -m src.bot backtest --start 2024-01-01 --end 2024-12-31
```

### Cloud Management
```bash
# Connect to server
ssh root@YOUR_IP

# Check bot status
systemctl status rct-trader

# View logs
journalctl -u rct-trader -f

# Restart bot
systemctl restart rct-trader

# Health check
bash /home/rctbot/apps/RCTTrader/health_check.sh
```

---

## Configuration

### Minimum `.env` (Alert Mode)
```env
TRADING_MODE=alert
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_IDS=your_chat_id
```

### Full Configuration
See `.env.example` for all options.

---

## Alert Setup

### Telegram
1. Message [@BotFather](https://t.me/botfather)
2. Create new bot, get token
3. Message [@userinfobot](https://t.me/userinfobot) to get your chat ID
4. Add to `.env`

### Email (Gmail)
1. Enable 2FA on Gmail
2. Generate App Password
3. Add to `.env`

---

## Monitoring

### Check Bot Health
```bash
bash health_check.sh
```

### View Logs
```bash
# Real-time
journalctl -u rct-trader -f

# Last 100 lines
journalctl -u rct-trader -n 100

# Application logs
tail -f logs/rct_trader.log
```

### Resource Usage
```bash
htop        # CPU/Memory
df -h       # Disk space
free -h     # Memory
```

---

## Troubleshooting

### Bot won't start
```bash
# Check logs
journalctl -u rct-trader -n 50

# Test manually
python -m src.bot demo
```

### Out of memory
```bash
# Add 2GB swap
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Disk full
```bash
# Clean logs
sudo journalctl --vacuum-time=7d
```

---

## Next Steps

### Phase 1: Validation (Week 1-2)
- [ ] Run in alert mode
- [ ] Validate signals
- [ ] Tune confidence thresholds
- [ ] Add more companies if needed

### Phase 2: Paper Trading (Week 3-4)
- [ ] Create Alpaca account
- [ ] Switch to `TRADING_MODE=paper`
- [ ] Track performance
- [ ] Aim for: 20+ trades, >50% win rate

### Phase 3: Live Trading (Month 2+)
- [ ] Validate paper performance
- [ ] Switch to `TRADING_MODE=live`
- [ ] Start small position sizes
- [ ] Scale up gradually

---

## Costs

### Local (Your Computer)
- **$0** but not 24/7

### Cloud VPS
| Provider | Monthly |
|----------|---------|
| Oracle Cloud | **FREE** |
| Vultr | $5 |
| DigitalOcean | $6 |
| Linode | $5 |

### Optional Paid Services
| Service | Cost | When to Add |
|---------|------|-------------|
| Polygon.io | $29/mo | Need tick data |
| Alpha Vantage | $50/mo | More fundamentals |
| UptimeRobot | Free-$8/mo | Monitoring |

---

## Support & Resources

### Documentation
- [README.md](README.md) - Main docs
- [QUICK_DEPLOY.md](QUICK_DEPLOY.md) - Fast deployment
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Complete guide
- [CLOUD_PROVIDERS.md](CLOUD_PROVIDERS.md) - Choose provider

### Commands
```bash
# Help
python -m src.bot --help

# Check status
systemctl status rct-trader

# View logs
journalctl -u rct-trader -f
```

---

## Success Checklist

### Week 1
- [ ] Bot running locally
- [ ] Demo works
- [ ] Telegram alerts working

### Week 2
- [ ] Deployed to cloud
- [ ] Running 24/7
- [ ] Receiving real alerts

### Week 3
- [ ] Paper trading enabled
- [ ] 10+ trades executed
- [ ] Tracking performance

### Week 4
- [ ] 20+ trades
- [ ] Win rate > 50%
- [ ] Ready for live trading

---

## You're Ready! 🚀

Start with:
1. `python -m src.bot demo` (local test)
2. Deploy to cloud ([QUICK_DEPLOY.md](QUICK_DEPLOY.md))
3. Monitor and iterate

**Questions?** Check the logs: `journalctl -u rct-trader -f`

Happy trading! 📈
