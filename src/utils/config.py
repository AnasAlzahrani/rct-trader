"""Configuration management using Pydantic Settings."""

from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import List, Optional
from enum import Enum


class TradingMode(str, Enum):
    """Trading modes for the bot."""
    ALERT = "alert"           # Generate alerts only
    PAPER = "paper"           # Paper trading
    LIVE = "live"             # Live trading with real money


class RiskProfile(str, Enum):
    """Risk profiles for position sizing."""
    CONSERVATIVE = "conservative"   # 1-2% per trade
    MODERATE = "moderate"           # 3-4% per trade
    AGGRESSIVE = "aggressive"       # 5%+ per trade


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # App Settings
    APP_NAME: str = "RCT Trader"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, description="Enable debug mode")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    
    # Trading Settings
    TRADING_MODE: TradingMode = Field(default=TradingMode.ALERT)
    RISK_PROFILE: RiskProfile = Field(default=RiskProfile.MODERATE)
    INITIAL_CAPITAL: float = Field(default=100000.0, description="Initial portfolio value")
    
    # Signal Thresholds
    MIN_CONFIDENCE: float = Field(default=0.55, ge=0.0, le=1.0)
    STRONG_BUY_THRESHOLD: float = Field(default=0.75, ge=0.0, le=1.0)
    BUY_THRESHOLD: float = Field(default=0.68, ge=0.0, le=1.0)
    SELL_THRESHOLD: float = Field(default=0.60, ge=0.0, le=1.0)
    STRONG_SELL_THRESHOLD: float = Field(default=0.75, ge=0.0, le=1.0)
    
    # Risk Management
    MAX_POSITION_SIZE_PCT: float = Field(default=0.05, ge=0.0, le=1.0)
    MAX_SECTOR_EXPOSURE_PCT: float = Field(default=0.20, ge=0.0, le=1.0)
    HARD_STOP_LOSS_PCT: float = Field(default=0.10, ge=0.0, le=1.0, description="Hard stop loss at -10%")
    MIN_MARKET_CAP: float = Field(default=20e9, description="Minimum market cap in USD ($20B)")
    MAX_DAILY_LOSS_PCT: float = Field(default=0.03, ge=0.0, le=1.0)
    MAX_WEEKLY_LOSS_PCT: float = Field(default=0.08, ge=0.0, le=1.0)
    MIN_LIQUIDITY_USD: int = Field(default=100_000)
    
    # V2 Risk Management
    TRAILING_STOP_ATR_MULT: float = Field(default=2.5, description="ATR multiplier for trailing stops")
    MAX_HOLD_DAYS: int = Field(default=10, description="Max days to hold a catalyst position")
    CIRCUIT_BREAKER_DRAWDOWN: float = Field(default=0.08, ge=0.0, le=0.5, description="Pause trading at this drawdown")
    MIN_VOLUME_RATIO: float = Field(default=1.3, description="Min volume/avg ratio for entry confirmation")
    ENABLE_TRAILING_STOPS: bool = Field(default=True)
    ENABLE_TIME_EXITS: bool = Field(default=True)
    ENABLE_SCALED_EXITS: bool = Field(default=True)
    
    # Database
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///data/rct_trader.db")
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    
    # API Keys
    ALPACA_API_KEY: Optional[str] = None
    ALPACA_SECRET_KEY: Optional[str] = None
    ALPACA_PAPER: bool = Field(default=True)
    
    FINNHUB_API_KEY: Optional[str] = None
    POLYGON_API_KEY: Optional[str] = None
    
    # Alert Settings
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_IDS: List[str] = Field(default_factory=list)
    
    EMAIL_SMTP_HOST: str = Field(default="smtp.gmail.com")
    EMAIL_SMTP_PORT: int = Field(default=587)
    EMAIL_USERNAME: Optional[str] = None
    EMAIL_PASSWORD: Optional[str] = None
    EMAIL_TO: List[str] = Field(default_factory=list)
    
    DISCORD_WEBHOOK_URL: Optional[str] = None
    
    # Data Sources
    CLINICAL_TRIALS_BASE_URL: str = Field(default="https://clinicaltrials.gov/api/v2")
    CLINICAL_TRIALS_RATE_LIMIT: float = Field(default=0.34, description="Seconds between requests")
    
    # Monitoring
    ENABLE_PROMETHEUS: bool = Field(default=False)
    PROMETHEUS_PORT: int = Field(default=9090)
    
    # Feature Flags
    ENABLE_ML_PREDICTION: bool = Field(default=True)
    ENABLE_SENTIMENT_ANALYSIS: bool = Field(default=False)
    ENABLE_SEC_FILINGS: bool = Field(default=True)
    
    @validator("TELEGRAM_CHAT_IDS", "EMAIL_TO", pre=True)
    def parse_comma_separated(cls, v):
        """Parse comma-separated string into list."""
        if isinstance(v, (int, float)):
            return [str(v)]
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v
    
    @property
    def base_risk_pct(self) -> float:
        """Get base risk percentage based on risk profile."""
        risk_map = {
            RiskProfile.CONSERVATIVE: 0.015,
            RiskProfile.MODERATE: 0.03,
            RiskProfile.AGGRESSIVE: 0.05,
        }
        return risk_map.get(self.RISK_PROFILE, 0.03)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()
