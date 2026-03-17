"""Main bot orchestrator for RCT Trader."""

import asyncio
import gc
import signal
import sys
from datetime import datetime, timedelta
from typing import List, Optional
from contextlib import asynccontextmanager

from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from src.utils.config import settings
from src.data_sources.clinical_trials import get_clinical_trials_client, TrialData
from src.data_sources.market_data import get_market_data_client
from src.data_sources.company_mapper import get_company_mapper
from src.analysis.signal_generator import get_signal_generator, TradingSignal
from src.analysis.event_study import get_event_study_analyzer
from src.analysis.risk_manager import get_risk_manager
from src.alerts.notifier import get_notifier


# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    level=settings.LOG_LEVEL,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)
logger.add(
    "logs/rct_trader.log",
    rotation="1 day",
    retention="30 days",
    level="DEBUG"
)

console = Console()


class RCTraderBot:
    """Main trading bot orchestrator."""
    
    def __init__(self):
        self.ct_client = get_clinical_trials_client()
        self.market_client = get_market_data_client()
        self.company_mapper = get_company_mapper()
        self.signal_generator = get_signal_generator()
        self.event_study = get_event_study_analyzer()
        self.notifier = get_notifier()
        self.risk_manager = get_risk_manager()
        self.scheduler = AsyncIOScheduler()
        
        self._running = False
        self._signals_generated: List[TradingSignal] = []
        self._open_positions: dict = {}  # ticker -> {entry_price, entry_time, shares}
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
        await self.ct_client.close()
    
    async def initialize(self):
        """Initialize the bot."""
        console.print(Panel.fit(
            f"[bold blue]RCT Trader v{settings.APP_VERSION}[/bold blue]\n"
            f"[green]Mode: {settings.TRADING_MODE.value}[/green] | "
            f"[green]Risk: {settings.RISK_PROFILE.value}[/green]",
            title="🚀 Starting Up",
            border_style="blue"
        ))
        
        # Test connections
        await self._test_connections()
        
        logger.info("Bot initialized successfully")
    
    async def _test_connections(self):
        """Test all data source connections."""
        tests = []
        
        # Test ClinicalTrials.gov
        try:
            async with self.ct_client:
                result = await self.ct_client.search_studies(limit=1)
                tests.append(("ClinicalTrials.gov", "✅ Connected", "green"))
        except Exception as e:
            tests.append(("ClinicalTrials.gov", f"❌ Error: {e}", "red"))
        
        # Test market data
        try:
            price = await self.market_client.get_current_price("PFE")
            if price:
                tests.append(("Yahoo Finance", "✅ Connected", "green"))
            else:
                tests.append(("Yahoo Finance", "⚠️ No data", "yellow"))
        except Exception as e:
            tests.append(("Yahoo Finance", f"❌ Error: {e}", "red"))
        
        # Display results
        table = Table(title="Connection Status", box=box.ROUNDED)
        table.add_column("Service", style="cyan")
        table.add_column("Status", style="bold")
        
        for service, status, color in tests:
            table.add_row(service, f"[{color}]{status}[/{color}]")
        
        console.print(table)
    
    async def scan_trials(
        self,
        hours_back: int = 24,
        min_phase: str = "PHASE2"
    ) -> List[TradingSignal]:
        """Scan for recent trial events and generate signals."""
        console.print(f"\n[bold]Scanning for trials updated in last {hours_back} hours...[/bold]")
        
        signals = []
        trials_checked = 0
        
        try:
            async with self.ct_client:
                async for trial in self.ct_client.get_recent_updates(
                    hours=hours_back,
                    min_phase=min_phase
                ):
                    trials_checked += 1
                    
                    # Map sponsor to ticker
                    if not trial.sponsor:
                        continue
                    
                    ticker = self.company_mapper.get_ticker(trial.sponsor)
                    if not ticker:
                        # Try collaborators
                        for collab in trial.collaborators:
                            ticker = self.company_mapper.get_ticker(collab)
                            if ticker:
                                break
                    
                    if not ticker:
                        logger.debug(f"No ticker found for sponsor: {trial.sponsor}")
                        continue
                    
                    # Create trial event
                    from src.database.models import TrialEvent, Trial as TrialModel, EventType
                    
                    trial_model = TrialModel(
                        nct_id=trial.nct_id,
                        phase=trial.phase,
                        overall_status=trial.overall_status,
                        therapeutic_area=trial.conditions[0] if trial.conditions else "Unknown",
                        has_results=trial.has_results
                    )
                    
                    # Detect event type from trial status
                    event_type = self._classify_event(trial)
                    
                    event = TrialEvent(
                        event_type=event_type,
                        event_date=trial.first_posted_date or datetime.now(),
                        trial=trial_model
                    )
                    
                    # Create company object
                    company_info = self.company_mapper.get_company_info(ticker)
                    from src.database.models import Company
                    company = Company(
                        ticker=ticker,
                        name=company_info.name if company_info else trial.sponsor,
                        market_cap_bucket=company_info.market_cap_bucket if company_info else "unknown"
                    )
                    
                    # Generate signal
                    signal = await self.signal_generator.generate_signal(event, company)
                    if signal:
                        signals.append(signal)
                        console.print(f"  [green]✓[/green] Signal generated for {ticker}: {signal.signal_type.value} ({signal.confidence:.0%})")
                    
                    # Memory management: GC every 20 trials
                    if trials_checked % 20 == 0:
                        gc.collect()
        
        except Exception as e:
            logger.error(f"Error scanning trials: {e}")
        
        console.print(f"\n[bold]Checked {trials_checked} trials, generated {len(signals)} signals[/bold]")
        return signals
    
    async def process_signals(self, signals: List[TradingSignal]):
        """Process generated signals (send alerts, execute trades)."""
        if not signals:
            console.print("[yellow]No signals to process[/yellow]")
            return
        
        # Filter: only actionable signals (skip HOLD for alerts)
        actionable = [s for s in signals if s.signal_type.value != "hold"]
        hold_count = len(signals) - len(actionable)
        if hold_count:
            console.print(f"[dim]Filtered out {hold_count} HOLD signals[/dim]")
        
        if not actionable:
            console.print("[yellow]No actionable signals (all HOLD)[/yellow]")
            return
        
        for signal in actionable:
            # Send alert
            await self.notifier.send_signal_alert(signal)
            
            # Store signal
            self._signals_generated.append(signal)
            
            # Execute trade if in paper/live mode
            if settings.TRADING_MODE.value in ["paper", "live"]:
                await self._execute_trade(signal)
        
        # Save signals to dashboard JSON and trigger redeploy
        self._save_signals_to_dashboard(actionable)
        self._redeploy_dashboard()
    
    def _save_signals_to_dashboard(self, signals: List[TradingSignal]):
        """Save signals to dashboard JSON file for the web dashboard."""
        import json
        import os
        
        dashboard_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'rct-dashboard', 'data', 'signals.json'
        )
        
        # Load existing signals
        existing = []
        try:
            if os.path.exists(dashboard_path):
                with open(dashboard_path, 'r') as f:
                    existing = json.load(f)
        except Exception:
            existing = []
        
        # Append new signals
        for s in signals:
            ta_data = {}
            if hasattr(s, 'ta') and s.ta:
                ta_data = {
                    'rsi_14': s.ta.rsi_14,
                    'rsi_zone': s.ta.rsi_zone,
                    'macd_crossover': s.ta.macd_crossover,
                    'macd_trend': s.ta.macd_trend,
                    'volume_ratio': s.ta.volume_ratio,
                    'volume_surge': s.ta.volume_surge,
                    'rsi_divergence': s.ta.rsi_divergence,
                    'macd_divergence': s.ta.macd_divergence,
                    'ta_verdict': s.ta.ta_verdict,
                    'ta_score': round(s.ta.ta_score, 3),
                    'ta_reasons': s.ta.ta_reasons[:5],
                }
            
            entry = {
                'timestamp': datetime.now().isoformat(),
                'ticker': s.ticker,
                'signal_type': s.signal_type.value,
                'confidence': round(s.confidence, 3),
                'entry_price': float(s.entry_price) if s.entry_price else None,
                'target_price': float(s.target_price) if s.target_price else None,
                'stop_loss': float(s.stop_loss) if s.stop_loss else None,
                'position_size_pct': round(s.position_size_pct, 4) if s.position_size_pct else None,
                'catalyst': s.event.event_type.value.replace('_', ' ').title() if s.event else '',
                'reasoning': s.reasoning[:200] if s.reasoning else '',
                'nct_id': s.event.trial.nct_id if s.event and s.event.trial else None,
                'phase': s.event.trial.phase if s.event and s.event.trial else None,
                'therapeutic_area': s.event.trial.therapeutic_area if s.event and s.event.trial else None,
                'technical': ta_data,
            }
            existing.append(entry)
        
        # Keep last 500 signals max
        existing = existing[-500:]
        
        try:
            os.makedirs(os.path.dirname(dashboard_path), exist_ok=True)
            with open(dashboard_path, 'w') as f:
                json.dump(existing, f, indent=2)
            console.print(f"[dim]📊 Saved {len(signals)} signals to dashboard[/dim]")
        except Exception as e:
            logger.warning(f"Failed to save signals to dashboard: {e}")

    def _redeploy_dashboard(self):
        """Trigger Vercel dashboard redeploy with updated signal data."""
        import subprocess
        try:
            result = subprocess.run(
                ['bash', '/root/.openclaw/workspace/rct-dashboard/deploy.sh'],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                console.print("[dim]🌐 Dashboard redeployed[/dim]")
            else:
                logger.warning(f"Dashboard deploy failed: {result.stderr[:200]}")
        except Exception as e:
            logger.warning(f"Dashboard deploy error: {e}")

    def _check_sector_concentration(self, signal: TradingSignal, positions: list, portfolio_value: float) -> bool:
        """[IMPROVEMENT 6] Check if adding this position would exceed 20% sector concentration.
        Returns True if trade is allowed, False if it would exceed the cap.
        """
        sector = None
        if signal.event and signal.event.trial and signal.event.trial.therapeutic_area:
            sector = signal.event.trial.therapeutic_area.lower().strip()
        
        if not sector or portfolio_value <= 0:
            return True  # Can't determine sector, allow trade
        
        # Calculate current sector exposure from existing positions
        sector_exposure = 0.0
        for pos in positions:
            # We tag positions by symbol; we'd need to look up their sector
            # For now, count all positions' market_value  
            pos_sector = self._get_position_sector(pos.get('symbol', ''))
            if pos_sector and pos_sector.lower().strip() == sector:
                sector_exposure += abs(float(pos.get('market_value', 0)))
        
        # Add proposed position value
        proposed_value = portfolio_value * (signal.position_size_pct or 0.02)
        new_exposure = (sector_exposure + proposed_value) / portfolio_value
        
        if new_exposure > settings.MAX_SECTOR_EXPOSURE_PCT:
            logger.info(f"Sector cap hit: {sector} would be {new_exposure:.1%} (max {settings.MAX_SECTOR_EXPOSURE_PCT:.0%})")
            console.print(f"[yellow]⚠ Skipping {signal.ticker}: sector '{sector}' exposure would be {new_exposure:.1%} > {settings.MAX_SECTOR_EXPOSURE_PCT:.0%} cap[/yellow]")
            return False
        return True

    def _get_position_sector(self, ticker: str) -> Optional[str]:
        """Look up therapeutic area/sector for a ticker from company mapper."""
        try:
            info = self.company_mapper.get_company_info(ticker)
            return info.sector if info else None
        except Exception:
            return None

    async def _check_hard_stop_loss(self, headers: dict, base_url: str):
        """[IMPROVEMENT 1] Check all positions for hard -10% stop loss and exit if breached."""
        import requests
        try:
            pos_resp = requests.get(f'{base_url}/v2/positions', headers=headers, timeout=10)
            if pos_resp.status_code != 200:
                return
            
            positions = pos_resp.json()
            for pos in positions:
                unrealized_plpc = float(pos.get('unrealized_plpc', 0))  # P/L percentage
                if unrealized_plpc <= -settings.HARD_STOP_LOSS_PCT:
                    symbol = pos.get('symbol', '?')
                    qty = pos.get('qty', '0')
                    side = 'sell' if float(qty) > 0 else 'buy'  # Close the position
                    
                    console.print(f"[red]🛑 HARD STOP: {symbol} down {unrealized_plpc:.1%} — closing position[/red]")
                    
                    order = {
                        'symbol': symbol,
                        'qty': str(abs(int(float(qty)))),
                        'side': side,
                        'type': 'market',
                        'time_in_force': 'day',
                    }
                    order_resp = requests.post(f'{base_url}/v2/orders', headers=headers, json=order, timeout=10)
                    if order_resp.status_code in [200, 201]:
                        console.print(f"[red]🛑 Hard stop executed: {side.upper()} {qty} x {symbol}[/red]")
                        trade_msg = f"🛑 HARD STOP LOSS\n{side.upper()} {qty} x {symbol}\nP/L: {unrealized_plpc:.1%}"
                        await self.notifier.send_raw_message(trade_msg)
                    else:
                        console.print(f"[red]✗ Hard stop order failed for {symbol}: {order_resp.status_code}[/red]")
        except Exception as e:
            logger.error(f"Hard stop loss check error: {e}")

    async def _execute_trade(self, signal: TradingSignal):
        """Execute trade through Alpaca paper trading API."""
        import os
        import requests
        
        api_key = os.getenv('ALPACA_API_KEY', '') or (settings.ALPACA_API_KEY or '')
        secret_key = os.getenv('ALPACA_SECRET_KEY', '') or (settings.ALPACA_SECRET_KEY or '')
        is_paper = os.getenv('ALPACA_PAPER', 'true').lower() == 'true' or getattr(settings, 'ALPACA_PAPER', True)
        base_url = 'https://paper-api.alpaca.markets' if is_paper else 'https://api.alpaca.markets'
        
        if not api_key or not secret_key:
            console.print(f"[yellow]⚠ No Alpaca credentials — skipping trade for {signal.ticker}[/yellow]")
            return
        
        headers = {
            'APCA-API-KEY-ID': api_key,
            'APCA-API-SECRET-KEY': secret_key,
            'Content-Type': 'application/json',
        }
        
        # [IMPROVEMENT 1] Check hard stop loss on all positions before new trades
        await self._check_hard_stop_loss(headers, base_url)
        
        # Determine side and position size
        is_buy = signal.signal_type.value in ["strong_buy", "buy"]
        is_sell = signal.signal_type.value in ["strong_sell", "sell"]
        
        if not (is_buy or is_sell):
            return
        
        try:
            # Get account for position sizing
            acct_resp = requests.get(f'{base_url}/v2/account', headers=headers, timeout=10)
            if acct_resp.status_code != 200:
                console.print(f"[red]✗ Alpaca account error: {acct_resp.status_code}[/red]")
                return
            
            acct = acct_resp.json()
            cash = float(acct.get('cash', 0))
            
            if is_buy:
                portfolio_value = float(acct.get('portfolio_value', cash))
                
                # [IMPROVEMENT 6] Check sector concentration cap before trading
                pos_resp = requests.get(f'{base_url}/v2/positions', headers=headers, timeout=10)
                positions = pos_resp.json() if pos_resp.status_code == 200 else []
                if not self._check_sector_concentration(signal, positions, portfolio_value):
                    return
                
                # [IMPROVEMENT 5] Use tiered position size from signal
                position_size = portfolio_value * (signal.position_size_pct or 0.02)
                
                # Calculate shares (use current price from signal or market)
                if signal.entry_price and signal.entry_price > 0:
                    qty = max(1, int(position_size / float(signal.entry_price)))
                else:
                    qty = 1
                
                order = {
                    'symbol': signal.ticker,
                    'qty': str(qty),
                    'side': 'buy',
                    'type': 'market',
                    'time_in_force': 'day',
                }
                
            elif is_sell:
                # Check if we have a position to sell
                pos_resp = requests.get(f'{base_url}/v2/positions/{signal.ticker}', headers=headers, timeout=10)
                if pos_resp.status_code != 200:
                    console.print(f"[yellow]📘 No position in {signal.ticker} to sell — skipping[/yellow]")
                    return
                
                pos = pos_resp.json()
                qty = pos.get('qty', '0')
                if int(float(qty)) <= 0:
                    return
                
                order = {
                    'symbol': signal.ticker,
                    'qty': qty,
                    'side': 'sell',
                    'type': 'market',
                    'time_in_force': 'day',
                }
            
            # Place the order
            order_resp = requests.post(f'{base_url}/v2/orders', headers=headers, json=order, timeout=10)
            
            if order_resp.status_code in [200, 201]:
                result = order_resp.json()
                side_emoji = "🟢" if is_buy else "🔴"
                console.print(
                    f"[bold]{side_emoji} Paper trade executed![/bold] "
                    f"{order['side'].upper()} {order['qty']} x {signal.ticker} "
                    f"(Order ID: {result.get('id', 'N/A')[:8]}...)"
                )
                
                # Also send trade notification via Telegram
                trade_msg = (
                    f"{side_emoji} Paper Trade Executed\n"
                    f"{'BUY' if is_buy else 'SELL'} {order['qty']} x {signal.ticker}\n"
                    f"Signal: {signal.signal_type.value.upper()} ({signal.confidence:.0%})\n"
                    f"Order ID: {result.get('id', 'N/A')[:12]}"
                )
                await self.notifier.send_raw_message(trade_msg)
                
                # [V2] Set up trailing stop and exit plan for buy orders
                if is_buy and signal.entry_price:
                    entry_f = float(signal.entry_price)
                    atr_data = await self.risk_manager.calculate_atr(signal.ticker)
                    atr_val = atr_data.atr_14 if atr_data else entry_f * 0.03
                    
                    self.risk_manager.create_trailing_stop(
                        signal.ticker, entry_f, atr_val,
                        multiplier=2.5,
                        initial_stop_pct=float(signal.entry_price - signal.stop_loss) / entry_f if signal.stop_loss else 0.05
                    )
                    
                    event_type = signal.event.event_type.value if signal.event else "default"
                    self.risk_manager.create_exit_plan(signal.ticker, entry_f, event_type)
                    
                    logger.info(f"[V2] Trailing stop + exit plan set for {signal.ticker}")
                    
            else:
                error = order_resp.json() if order_resp.headers.get('content-type', '').startswith('application/json') else order_resp.text
                console.print(f"[red]✗ Order failed for {signal.ticker}: {order_resp.status_code} — {error}[/red]")
                
        except Exception as e:
            console.print(f"[red]✗ Trade execution error for {signal.ticker}: {e}[/red]")
    
    async def run_backtest(
        self,
        start_date: datetime,
        end_date: datetime,
        tickers: Optional[List[str]] = None
    ):
        """Run backtest on historical data."""
        console.print(Panel.fit(
            f"[bold]Running Backtest[/bold]\n"
            f"Period: {start_date.date()} to {end_date.date()}",
            border_style="blue"
        ))
        
        # TODO: Implement full backtest
        console.print("[yellow]Backtest implementation in progress...[/yellow]")
    
    async def run_continuous(self):
        """Run bot continuously with scheduled scans."""
        console.print("\n[bold green]Starting continuous mode...[/bold green]")
        console.print("Press Ctrl+C to stop\n")
        
        self._running = True
        
        # Schedule hourly scans
        self.scheduler.add_job(
            self._scheduled_scan,
            CronTrigger(minute=0),  # Every hour
            id="hourly_scan",
            replace_existing=True
        )
        
        # Schedule position monitoring every 5 minutes during market hours
        self.scheduler.add_job(
            self._monitor_positions,
            CronTrigger(minute="*/5", hour="14-21", day_of_week="mon-fri"),  # UTC ~9:00-16:00 ET
            id="position_monitor",
            replace_existing=True
        )
        
        # Schedule daily summary
        self.scheduler.add_job(
            self._daily_summary,
            CronTrigger(hour=16, minute=30),  # 4:30 PM
            id="daily_summary",
            replace_existing=True
        )
        
        self.scheduler.start()
        
        # Run initial scan
        await self._scheduled_scan()
        
        # Keep running
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
    
    async def _scheduled_scan(self):
        """Scheduled scan job."""
        logger.info("Running scheduled scan")
        signals = await self.scan_trials(hours_back=1)
        await self.process_signals(signals)
    
    async def _monitor_positions(self):
        """Monitor open positions for trailing stops, time exits, and profit targets."""
        import os
        import requests
        
        api_key = os.getenv('ALPACA_API_KEY', '') or (settings.ALPACA_API_KEY or '')
        secret_key = os.getenv('ALPACA_SECRET_KEY', '') or (settings.ALPACA_SECRET_KEY or '')
        if not api_key or not secret_key:
            return
        
        is_paper = os.getenv('ALPACA_PAPER', 'true').lower() == 'true'
        base_url = 'https://paper-api.alpaca.markets' if is_paper else 'https://api.alpaca.markets'
        headers = {
            'APCA-API-KEY-ID': api_key,
            'APCA-API-SECRET-KEY': secret_key,
        }
        
        try:
            # Get account for circuit breaker
            acct_resp = requests.get(f'{base_url}/v2/account', headers=headers, timeout=10)
            if acct_resp.status_code == 200:
                acct = acct_resp.json()
                portfolio_value = float(acct.get('portfolio_value', 0))
                self.risk_manager.update_portfolio_value(portfolio_value)
                
                if self.risk_manager.check_circuit_breaker(portfolio_value):
                    await self.notifier.send_raw_message(
                        "🚨 CIRCUIT BREAKER: Trading paused due to drawdown. "
                        "Manual review required."
                    )
            
            # Get open positions
            pos_resp = requests.get(f'{base_url}/v2/positions', headers=headers, timeout=10)
            if pos_resp.status_code != 200:
                return
            
            positions = pos_resp.json()
            
            for pos in positions:
                ticker = pos['symbol']
                current_price = float(pos['current_price'])
                entry_price = float(pos['avg_entry_price'])
                qty = int(float(pos['qty']))
                
                # 1. Check time-based exit (10 days max hold)
                if self.risk_manager.check_time_exit(ticker, max_hold_days=10):
                    logger.info(f"⏰ Time exit for {ticker}")
                    self._close_position(ticker, qty, base_url, headers, "time_exit")
                    continue
                
                # 2. Update trailing stop
                stop_price, triggered = self.risk_manager.update_trailing_stop(ticker, current_price)
                if triggered:
                    logger.info(f"📉 Trailing stop hit for {ticker} at ${stop_price:.2f}")
                    self._close_position(ticker, qty, base_url, headers, "trailing_stop")
                    continue
                
                # 3. Check scaled profit targets
                if ticker in self.risk_manager._exit_plans:
                    plan = self.risk_manager._exit_plans[ticker]
                    exits = plan.check_targets(current_price)
                    for target_pct, fraction in exits:
                        sell_qty = max(1, int(qty * fraction))
                        logger.info(f"💰 Profit target {target_pct:.0%} hit for {ticker}, selling {sell_qty} shares")
                        self._close_position(ticker, sell_qty, base_url, headers, f"profit_target_{target_pct:.0%}")
            
        except Exception as e:
            logger.error(f"Position monitoring error: {e}")
    
    def _close_position(self, ticker: str, qty: int, base_url: str, headers: dict, reason: str):
        """Close a position (full or partial)."""
        import requests
        try:
            order = {
                'symbol': ticker,
                'qty': str(qty),
                'side': 'sell',
                'type': 'market',
                'time_in_force': 'day',
            }
            resp = requests.post(f'{base_url}/v2/orders', headers={**headers, 'Content-Type': 'application/json'},
                                 json=order, timeout=10)
            if resp.status_code in [200, 201]:
                console.print(f"[bold]🔄 Closed {qty}x {ticker} — reason: {reason}[/bold]")
                if qty == int(float(resp.json().get('qty', qty))):
                    self.risk_manager.remove_position(ticker)
            else:
                logger.error(f"Failed to close {ticker}: {resp.status_code}")
        except Exception as e:
            logger.error(f"Error closing {ticker}: {e}")
    
    def _classify_event(self, trial) -> 'EventType':
        """Classify trial event type based on status and data."""
        from src.database.models import EventType
        
        status = (trial.overall_status or "").upper()
        
        # Results posted = highest impact
        if trial.has_results:
            return EventType.RESULTS_POSTED
        
        # Trial suspended
        if status == "SUSPENDED":
            return EventType.TRIAL_SUSPENDED
        
        # Trial terminated or withdrawn
        if status in ("TERMINATED", "WITHDRAWN"):
            return EventType.TRIAL_TERMINATED
        
        # Completed (no results yet)
        if status == "COMPLETED":
            return EventType.PRIMARY_COMPLETION
        
        # Active but no longer recruiting = enrollment complete
        if status == "ACTIVE_NOT_RECRUITING":
            return EventType.ENROLLMENT_COMPLETE
        
        # Default: new/recruiting trial
        return EventType.NEW_TRIAL
    
    async def _daily_summary(self):
        """Send daily summary."""
        await self.notifier.send_summary(self._signals_generated, "daily")
        self._signals_generated = []  # Reset for next day
    
    async def stop(self):
        """Stop the bot."""
        console.print("\n[yellow]Shutting down...[/yellow]")
        self._running = False
        
        if self.scheduler.running:
            self.scheduler.shutdown()
        
        await self.ct_client.__aexit__(None, None, None)
        
        console.print("[green]Bot stopped[/green]")
    
    async def demo(self):
        """Run demo with mock data."""
        console.print(Panel.fit(
            "[bold]Demo Mode[/bold]\n"
            "Generating sample signals with mock data",
            border_style="green"
        ))
        
        # Create mock signals
        from src.database.models import TrialEvent, Trial, EventType, Company
        from src.analysis.signal_generator import SignalScore
        
        mock_signals = []
        
        scenarios = [
            ("MRNA", "Phase 3 results posted", EventType.RESULTS_POSTED, 0.78),
            ("SGEN", "New Phase 3 trial registered", EventType.NEW_TRIAL, 0.65),
            ("VRTX", "FDA approval received", EventType.FDA_APPROVAL, 0.85),
            ("BIIB", "Trial terminated", EventType.TRIAL_TERMINATED, 0.72),
        ]
        
        for ticker, description, event_type, confidence in scenarios:
            trial = Trial(
                nct_id=f"NCT{hash(ticker) % 100000000:08d}",
                phase="PHASE3",
                therapeutic_area="Oncology"
            )
            
            event = TrialEvent(
                event_type=event_type,
                event_date=datetime.now(),
                trial=trial,
                description=description
            )
            
            company_info = self.company_mapper.get_company_info(ticker)
            company = Company(
                ticker=ticker,
                name=company_info.name if company_info else ticker,
                market_cap_bucket=company_info.market_cap_bucket if company_info else "mid"
            )
            
            signal = await self.signal_generator.generate_signal(event, company)
            if signal:
                mock_signals.append(signal)
        
        # Display results
        table = Table(title="Demo Signals", box=box.ROUNDED)
        table.add_column("Ticker", style="cyan")
        table.add_column("Signal", style="bold")
        table.add_column("Confidence", style="green")
        table.add_column("Entry", style="yellow")
        table.add_column("Target", style="green")
        table.add_column("Stop", style="red")
        
        for signal in mock_signals:
            table.add_row(
                signal.ticker,
                signal.signal_type.value.upper(),
                f"{signal.confidence:.0%}",
                f"${signal.entry_price}",
                f"${signal.target_price}",
                f"${signal.stop_loss}"
            )
        
        console.print(table)
        
        # Send alerts
        for signal in mock_signals:
            await self.notifier.send_signal_alert(signal, channels=["console"])


# CLI Commands
@click.group()
def cli():
    """RCT Trader - Clinical Trials Trading Bot"""
    pass


@cli.command()
def demo():
    """Run demo with mock data."""
    async def run():
        async with RCTraderBot() as bot:
            await bot.initialize()
            await bot.demo()
    
    asyncio.run(run())


@cli.command()
@click.option("--hours", "-h", default=24, help="Hours back to scan")
@click.option("--phase", "-p", default="PHASE2", help="Minimum trial phase")
def scan(hours: int, phase: str):
    """Run single scan for trial events."""
    async def run():
        async with RCTraderBot() as bot:
            await bot.initialize()
            signals = await bot.scan_trials(hours_back=hours, min_phase=phase)
            await bot.process_signals(signals)
    
    asyncio.run(run())


@cli.command()
def run():
    """Run bot continuously."""
    async def main():
        bot = RCTraderBot()
        
        # Setup signal handlers
        def signal_handler(sig, frame):
            asyncio.create_task(bot.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        await bot.initialize()
        await bot.run_continuous()
    
    asyncio.run(main())


@cli.command()
@click.option("--start", "-s", required=True, help="Start date (YYYY-MM-DD)")
@click.option("--end", "-e", required=True, help="End date (YYYY-MM-DD)")
@click.option("--tickers", "-t", help="Comma-separated tickers")
def backtest(start: str, end: str, tickers: Optional[str]):
    """Run backtest on historical data."""
    async def run():
        start_date = datetime.strptime(start, "%Y-%m-%d")
        end_date = datetime.strptime(end, "%Y-%m-%d")
        ticker_list = tickers.split(",") if tickers else None
        
        async with RCTraderBot() as bot:
            await bot.initialize()
            await bot.run_backtest(start_date, end_date, ticker_list)
    
    asyncio.run(run())


if __name__ == "__main__":
    cli()
