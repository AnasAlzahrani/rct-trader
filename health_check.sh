#!/bin/bash
# RCT Trader - Health Check Script
# Run this to check if your bot is healthy

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "=========================================="
echo "  RCT Trader - Health Check"
echo "=========================================="
echo ""

# Check if running as root for some checks
if [ "$EUID" -eq 0 ]; then
    IS_ROOT=true
else
    IS_ROOT=false
fi

# Function to print status
check_pass() {
    echo -e "${GREEN}✓${NC} $1"
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

check_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# 1. Check if service is running
echo "Checking Service Status..."
if systemctl is-active --quiet rct-trader; then
    check_pass "Bot service is running"
    
    # Get uptime
    UPTIME=$(systemctl show rct-trader --property=ActiveEnterTimestamp --value)
    if [ -n "$UPTIME" ]; then
        check_info "Service started: $UPTIME"
    fi
else
    check_fail "Bot service is NOT running"
    check_info "Start with: sudo systemctl start rct-trader"
fi
echo ""

# 2. Check Redis
echo "Checking Redis..."
if systemctl is-active --quiet redis; then
    check_pass "Redis is running"
else
    check_fail "Redis is NOT running"
    check_info "Start with: sudo systemctl start redis"
fi
echo ""

# 3. Check disk space
echo "Checking Disk Space..."
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -lt 80 ]; then
    check_pass "Disk usage: ${DISK_USAGE}%"
elif [ "$DISK_USAGE" -lt 90 ]; then
    check_warn "Disk usage: ${DISK_USAGE}% (getting full)"
else
    check_fail "Disk usage: ${DISK_USAGE}% (CRITICAL)"
fi
echo ""

# 4. Check memory
echo "Checking Memory..."
MEM_INFO=$(free | grep Mem)
MEM_TOTAL=$(echo $MEM_INFO | awk '{print $2}')
MEM_USED=$(echo $MEM_INFO | awk '{print $3}')
MEM_PERCENT=$((MEM_USED * 100 / MEM_TOTAL))

if [ "$MEM_PERCENT" -lt 80 ]; then
    check_pass "Memory usage: ${MEM_PERCENT}%"
elif [ "$MEM_PERCENT" -lt 90 ]; then
    check_warn "Memory usage: ${MEM_PERCENT}% (high)"
else
    check_fail "Memory usage: ${MEM_PERCENT}% (CRITICAL)"
fi
echo ""

# 5. Check logs for errors (last hour)
echo "Checking Recent Logs..."
if [ "$IS_ROOT" = true ]; then
    ERROR_COUNT=$(journalctl -u rct-trader --since "1 hour ago" -p err --no-pager 2>/dev/null | wc -l)
    if [ "$ERROR_COUNT" -eq 0 ]; then
        check_pass "No errors in last hour"
    else
        check_warn "Found $ERROR_COUNT error(s) in last hour"
        check_info "View with: sudo journalctl -u rct-trader --since '1 hour ago' -p err"
    fi
else
    check_info "Run as root to check logs: sudo $0"
fi
echo ""

# 6. Check database
echo "Checking Database..."
DB_FILE="/home/rctbot/apps/RCTTrader/data/rct_trader.db"
if [ -f "$DB_FILE" ]; then
    DB_SIZE=$(du -h "$DB_FILE" | cut -f1)
    check_pass "Database exists (${DB_SIZE})"
else
    check_warn "Database not found (will be created on first run)"
fi
echo ""

# 7. Check if bot is responsive (test with scan)
echo "Checking Bot Responsiveness..."
if [ "$IS_ROOT" = true ]; then
    # Check if process is actually doing work
    CPU_USAGE=$(ps -p $(pgrep -f "src.bot" 2>/dev/null) -o %cpu= 2>/dev/null | tr -d ' ')
    if [ -n "$CPU_USAGE" ]; then
        check_info "Current CPU usage: ${CPU_USAGE}%"
    fi
fi
echo ""

# 8. Check recent signals (if log exists)
echo "Checking Recent Signals..."
LOG_FILE="/home/rctbot/apps/RCTTrader/logs/rct_trader.log"
if [ -f "$LOG_FILE" ]; then
    SIGNAL_COUNT=$(grep -c "Signal generated" "$LOG_FILE" 2>/dev/null || echo "0")
    check_info "Total signals generated: $SIGNAL_COUNT"
    
    # Check last activity
    LAST_ACTIVITY=$(tail -5 "$LOG_FILE" 2>/dev/null | grep -E "(INFO|DEBUG)" | tail -1)
    if [ -n "$LAST_ACTIVITY" ]; then
        check_info "Last activity: $(echo $LAST_ACTIVITY | cut -d'|' -f1)"
    fi
else
    check_warn "Log file not found"
fi
echo ""

# 9. Check network connectivity
echo "Checking Network..."
if ping -c 1 -W 2 clinicaltrials.gov > /dev/null 2>&1; then
    check_pass "Can reach ClinicalTrials.gov"
else
    check_fail "Cannot reach ClinicalTrials.gov (network issue?)"
fi
echo ""

# 10. Check firewall
echo "Checking Firewall..."
if $IS_ROOT && command -v ufw &> /dev/null; then
    if ufw status | grep -q "Status: active"; then
        check_pass "Firewall is active"
    else
        check_warn "Firewall is not active"
    fi
fi
echo ""

# Summary
echo "=========================================="
echo "  Health Check Complete"
echo "=========================================="
echo ""
echo "Quick Commands:"
echo "  View logs:     sudo journalctl -u rct-trader -f"
echo "  Restart bot:   sudo systemctl restart rct-trader"
echo "  Check status:  sudo systemctl status rct-trader"
echo "  View resources: htop"
echo ""
