#!/bin/bash
# RCT Trader — 30-second demo
# Simulates typing for visual effect

type_slow() {
    for ((i=0; i<${#1}; i++)); do
        echo -n "${1:$i:1}"
        sleep 0.04
    done
    echo
}

clear
echo ""
echo "  🧪 RCT Trader — Clinical Trials Intelligence Monitor"
echo "  ====================================================="
echo ""
sleep 1.5

# Step 1: ARK Tracker
type_slow "$ python -m src.data_sources.ark_tracker"
sleep 0.5

cd /root/.openclaw/workspace/rct-trader
source venv/bin/activate

python3 -c "
import sys, os
sys.path.insert(0, '.')
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
from loguru import logger
logger.remove()
from src.data_sources.ark_tracker import ArkTracker
tracker = ArkTracker()
print()
print(tracker.get_summary())
print()
print('--- ARKG Top 10 Holdings ---')
fmt = '{:<8} {:>7} {:>12} {}'
print(fmt.format('Ticker', 'Weight', 'Value', 'Company'))
print('-' * 60)
for h in tracker.get_holdings('ARKG')[:10]:
    print(fmt.format(h.ticker, f'{h.weight:.2f}%', f'\${h.market_value/1e6:.1f}M', h.company))
" 2>/dev/null

sleep 3

echo ""
type_slow "$ python -m src.bot demo"
sleep 0.5

python3 -c "
import sys, time
sys.path.insert(0, '.')
from datetime import datetime

signals = [
    ('GILD', 'STRONG BUY', 76.5, 'Phase 3 Hep B results posted', 'Hepatology'),
    ('CRSP', 'BUY', 68.2, 'Phase 2 gene therapy completion', 'Gene Therapy'),
    ('PFE',  'HOLD', 52.1, 'Phase 3 enrollment update', 'Oncology'),
]

for sym, sig_type, conf, reason, area in signals:
    color = '\U0001f7e2' if 'BUY' in sig_type else '\U0001f7e1' if 'HOLD' in sig_type else '\U0001f534'
    border = '\u2500' * 60
    print(f'\n\u256d{border}\u256e')
    print(f'\u2502 {color} {sig_type}: {sym:<50}\u2502')
    print(f'\u2502 Confidence: {conf}%{\" \"*(47-len(str(conf)))}\u2502')
    print(f'\u2502 Reason: {reason:<51}\u2502')
    print(f'\u2502 Area: {area:<53}\u2502')
    ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M')
    print(f'\u2502 Time: {ts} UTC{\" \"*37}\u2502')
    print(f'\u2570{border}\u256f')
    time.sleep(1)
" 2>/dev/null

echo ""
echo "  🔗 github.com/AnasAlzahrani/rct-trader"
echo "  MIT Licensed — Fork it, improve it, build something better."
echo ""
sleep 3
