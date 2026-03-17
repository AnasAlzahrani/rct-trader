"""Multi-channel alert notification system."""

import asyncio
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from telegram import Bot
from discord_webhook import DiscordWebhook
from loguru import logger

from src.utils.config import settings
from src.analysis.signal_generator import TradingSignal


@dataclass
class AlertMessage:
    """Structured alert message."""
    title: str
    body: str
    priority: str  # high, medium, low
    metadata: Dict[str, Any]
    timestamp: datetime


class AlertNotifier:
    """Send alerts through multiple channels."""
    
    def __init__(self):
        self.telegram_bot: Optional[Bot] = None
        self._init_telegram()
    
    def _init_telegram(self):
        """Initialize Telegram bot."""
        if settings.TELEGRAM_BOT_TOKEN:
            try:
                self.telegram_bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
                logger.info("Telegram bot initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Telegram bot: {e}")
    
    async def send_signal_alert(
        self,
        signal: TradingSignal,
        channels: Optional[List[str]] = None
    ):
        """Send alert for a trading signal."""
        if channels is None:
            channels = ["console", "email", "telegram"]
        
        # Format the alert message
        message = self._format_signal_message(signal)
        
        # Send to each channel
        tasks = []
        
        if "console" in channels:
            tasks.append(self._send_console(message))
        
        if "email" in channels and settings.EMAIL_USERNAME:
            tasks.append(self._send_email(message))
        
        if "telegram" in channels and self.telegram_bot:
            tasks.append(self._send_telegram(message))
        
        if "discord" in channels and settings.DISCORD_WEBHOOK_URL:
            tasks.append(self._send_discord(message))
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    def _format_signal_message(self, signal: TradingSignal) -> AlertMessage:
        """Format trading signal into alert message."""
        emoji_map = {
            "strong_buy": "🚀",
            "buy": "📈",
            "hold": "➖",
            "sell": "📉",
            "strong_sell": "🔻"
        }
        
        emoji = emoji_map.get(signal.signal_type.value, "📊")
        priority = "high" if signal.confidence > 0.75 else "medium" if signal.confidence > 0.6 else "low"
        
        title = f"{emoji} {signal.signal_type.value.upper().replace('_', ' ')}: {signal.ticker}"
        
        # Technical analysis section
        ta_section = ""
        ta = getattr(signal, 'ta', None)
        if ta:
            ta_lines = [
                f"\n📉 Technical Analysis ({ta.ta_verdict.upper().replace('_', ' ')}):",
                f"  RSI(14): {ta.rsi_14 or '—'} ({ta.rsi_zone})",
                f"  MACD: {ta.macd_crossover.replace('_', ' ') if ta.macd_crossover != 'none' else ta.macd_trend}",
                f"  Volume: {ta.volume_ratio or '—'}x avg {'🔥 SURGE' if ta.volume_surge else ''}",
            ]
            if ta.rsi_divergence != "none":
                ta_lines.append(f"  RSI Divergence: {ta.rsi_divergence} {'🔥' if ta.rsi_divergence == 'bullish' else '⚠️'}")
            if ta.macd_divergence != "none":
                ta_lines.append(f"  MACD Divergence: {ta.macd_divergence}")
            if ta.ta_reasons:
                ta_lines.append(f"  Signals: {' | '.join(ta.ta_reasons[:3])}")
            ta_section = "\n".join(ta_lines)
        
        body = f"""
{emoji} {signal.signal_type.value.upper().replace('_', ' ')}: {signal.ticker}
{'='*50}

📋 Catalyst: {signal.event.event_type.value.replace('_', ' ').title()}
🎯 Confidence: {signal.confidence:.1%}

💰 Entry Price: ${signal.entry_price}
🎯 Target Price: ${signal.target_price} ({self._calculate_return(signal.entry_price, signal.target_price):+.1%})
🛑 Stop Loss: ${signal.stop_loss} ({self._calculate_return(signal.entry_price, signal.stop_loss):+.1%})
📊 Risk/Reward: {self._calculate_risk_reward(signal):.1f}

📐 Position Size: {signal.position_size_pct:.1%} of portfolio
{ta_section}

📊 Score Breakdown:
  • Catalyst: {signal.scores.catalyst_score:.0%}
  • Technical: {signal.scores.ta_score:.0%}
  • Company: {signal.scores.company_score:.0%}
  • Market: {signal.scores.market_score:.0%}
  • Timing: {signal.scores.timing_score:.0%}

💡 Reasoning:
{signal.reasoning}

⏰ Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}
⚡ Decision window: Act within 30 min of market open
"""
        
        return AlertMessage(
            title=title,
            body=body,
            priority=priority,
            metadata={
                "ticker": signal.ticker,
                "signal_type": signal.signal_type.value,
                "confidence": signal.confidence,
                "event_type": signal.event.event_type.value
            },
            timestamp=datetime.now()
        )
    
    def _calculate_return(self, entry: float, exit: float) -> float:
        """Calculate percentage return."""
        return (float(exit) - float(entry)) / float(entry)
    
    def _calculate_risk_reward(self, signal: TradingSignal) -> float:
        """Calculate risk/reward ratio."""
        upside = abs(float(signal.target_price) - float(signal.entry_price))
        downside = abs(float(signal.entry_price) - float(signal.stop_loss))
        if downside == 0:
            return 0
        return upside / downside
    
    async def _send_console(self, message: AlertMessage):
        """Send alert to console."""
        try:
            # Use rich for beautiful console output
            from rich.console import Console
            from rich.panel import Panel
            from rich.text import Text
            
            console = Console()
            
            color_map = {
                "high": "red",
                "medium": "yellow",
                "low": "green"
            }
            
            panel = Panel(
                Text(message.body),
                title=message.title,
                border_style=color_map.get(message.priority, "white")
            )
            
            console.print(panel)
            logger.info(f"Console alert sent: {message.title}")
            
        except ImportError:
            # Fallback to plain print
            print(f"\n{'='*60}")
            print(f"ALERT: {message.title}")
            print(f"{'='*60}")
            print(message.body)
            print(f"{'='*60}\n")
    
    async def _send_email(self, message: AlertMessage):
        """Send alert via email."""
        try:
            if not settings.EMAIL_USERNAME or not settings.EMAIL_PASSWORD:
                return
            
            # Create message
            msg = MIMEMultipart()
            msg["From"] = settings.EMAIL_USERNAME
            msg["To"] = ", ".join(settings.EMAIL_TO)
            msg["Subject"] = f"[RCT Trader] {message.title}"
            
            # Add body
            msg.attach(MIMEText(message.body, "plain"))
            
            # Send
            await aiosmtplib.send(
                msg,
                hostname=settings.EMAIL_SMTP_HOST,
                port=settings.EMAIL_SMTP_PORT,
                username=settings.EMAIL_USERNAME,
                password=settings.EMAIL_PASSWORD,
                start_tls=True
            )
            
            logger.info(f"Email alert sent: {message.title}")
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
    
    def _escape_markdownv2(self, text: str) -> str:
        """Escape all MarkdownV2 special characters."""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    async def _send_telegram(self, message: AlertMessage):
        """Send alert via Telegram."""
        try:
            if not self.telegram_bot or not settings.TELEGRAM_CHAT_IDS:
                return
            
            # Use plain text to avoid MarkdownV2 escaping issues
            text = message.body
            
            for chat_id in settings.TELEGRAM_CHAT_IDS:
                try:
                    await self.telegram_bot.send_message(
                        chat_id=chat_id,
                        text=text
                    )
                except Exception as e:
                    logger.error(f"Failed to send Telegram to {chat_id}: {e}")
            
            logger.info(f"Telegram alert sent: {message.title}")
            
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
    
    async def _send_discord(self, message: AlertMessage):
        """Send alert via Discord webhook."""
        try:
            if not settings.DISCORD_WEBHOOK_URL:
                return
            
            webhook = DiscordWebhook(
                url=settings.DISCORD_WEBHOOK_URL,
                content=f"**{message.title}**\n```{message.body}```"
            )
            
            webhook.execute()
            logger.info(f"Discord alert sent: {message.title}")
            
        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")
    
    async def send_raw_message(self, text: str):
        """Send a raw text message via Telegram."""
        try:
            if not self.telegram_bot or not settings.TELEGRAM_CHAT_IDS:
                return
            for chat_id in settings.TELEGRAM_CHAT_IDS:
                try:
                    await self.telegram_bot.send_message(chat_id=chat_id, text=text)
                except Exception as e:
                    logger.error(f"Failed to send raw Telegram to {chat_id}: {e}")
        except Exception as e:
            logger.error(f"Failed to send raw Telegram message: {e}")

    async def send_summary(
        self,
        signals: List[TradingSignal],
        period: str = "daily"
    ):
        """Send summary of signals."""
        if not signals:
            return
        
        title = f"📊 {period.title()} Signal Summary"
        
        body_lines = [
            f"Total Signals: {len(signals)}",
            f"Strong Buy: {sum(1 for s in signals if s.signal_type.value == 'strong_buy')}",
            f"Buy: {sum(1 for s in signals if s.signal_type.value == 'buy')}",
            f"Sell: {sum(1 for s in signals if s.signal_type.value == 'sell')}",
            f"Strong Sell: {sum(1 for s in signals if s.signal_type.value == 'strong_sell')}",
            "",
            "Signals by Ticker:"
        ]
        
        for signal in signals:
            body_lines.append(f"  • {signal.ticker}: {signal.signal_type.value} ({signal.confidence:.0%})")
        
        message = AlertMessage(
            title=title,
            body="\n".join(body_lines),
            priority="low",
            metadata={"signal_count": len(signals)},
            timestamp=datetime.now()
        )
        
        await self._send_console(message)
        
        if settings.EMAIL_USERNAME:
            await self._send_email(message)
    
    async def send_error_alert(self, error_message: str, component: str):
        """Send error notification."""
        message = AlertMessage(
            title=f"❌ Error in {component}",
            body=error_message,
            priority="high",
            metadata={"component": component},
            timestamp=datetime.now()
        )
        
        await self._send_console(message)
        
        if settings.EMAIL_USERNAME:
            await self._send_email(message)


# Singleton instance
_notifier: Optional[AlertNotifier] = None


def get_notifier() -> AlertNotifier:
    """Get singleton instance of AlertNotifier."""
    global _notifier
    if _notifier is None:
        _notifier = AlertNotifier()
    return _notifier
