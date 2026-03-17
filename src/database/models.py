"""Database models for RCT Trader."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, DateTime, Date, Boolean, 
    Text, ForeignKey, Enum, JSON, Index, UniqueConstraint, Numeric
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class EventType(str, PyEnum):
    """Types of clinical trial events."""
    NEW_TRIAL = "new_trial"
    PHASE_ADVANCE = "phase_advance"
    ENROLLMENT_COMPLETE = "enrollment_complete"
    PRIMARY_COMPLETION = "primary_completion"
    RESULTS_POSTED = "results_posted"
    TRIAL_TERMINATED = "trial_terminated"
    TRIAL_SUSPENDED = "trial_suspended"
    FDA_APPROVAL = "fda_approval"
    PROTOCOL_AMENDMENT = "protocol_amendment"


class SignalType(str, PyEnum):
    """Trading signal types."""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class TradeStatus(str, PyEnum):
    """Trade execution status."""
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ExitReason(str, PyEnum):
    """Reasons for exiting a trade."""
    PROFIT_TARGET = "profit_target"
    STOP_LOSS = "stop_loss"
    TIME_EXIT = "time_exit"
    CATALYST_CHANGE = "catalyst_change"
    MANUAL = "manual"
    TRAILING_STOP = "trailing_stop"


class Company(Base):
    """Pharmaceutical/Biotech company information."""
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    ticker = Column(String(20), nullable=False, unique=True, index=True)
    aliases = Column(JSON, default=list)  # Alternative names
    parent_company = Column(String(255), nullable=True)
    
    # Classification
    sector = Column(String(50), default="Biotechnology")
    industry = Column(String(100))
    market_cap_bucket = Column(String(20))  # small, mid, large
    
    # Financial metrics (updated periodically)
    market_cap = Column(Numeric(20, 2), nullable=True)
    enterprise_value = Column(Numeric(20, 2), nullable=True)
    cash_and_equivalents = Column(Numeric(20, 2), nullable=True)
    total_debt = Column(Numeric(20, 2), nullable=True)
    
    # Pipeline info
    pipeline_concentration = Column(Float, nullable=True)  # 0-1, revenue dependency
    num_active_trials = Column(Integer, default=0)
    
    # Metadata
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    trials = relationship("Trial", back_populates="company", lazy="dynamic")
    signals = relationship("Signal", back_populates="company", lazy="dynamic")
    trades = relationship("Trade", back_populates="company", lazy="dynamic")
    
    def __repr__(self):
        return f"<Company({self.ticker}: {self.name})>"


class Trial(Base):
    """Clinical trial information."""
    __tablename__ = "trials"
    
    id = Column(Integer, primary_key=True)
    nct_id = Column(String(20), unique=True, nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    
    # Trial identification
    brief_title = Column(Text)
    official_title = Column(Text)
    
    # Trial characteristics
    phase = Column(String(10), index=True)  # PHASE1, PHASE2, PHASE3, PHASE4
    overall_status = Column(String(50))  # Recruiting, Completed, Terminated, etc.
    
    # Therapeutic info
    conditions = Column(JSON, default=list)  # List of conditions
    interventions = Column(JSON, default=list)  # List of interventions
    therapeutic_area = Column(String(100), index=True)
    
    # Design
    study_type = Column(String(50))  # Interventional, Observational
    allocation = Column(String(50))  # Randomized, Non-Randomized
    intervention_model = Column(String(50))
    primary_purpose = Column(String(50))
    masking = Column(String(100))  # Blinding info
    
    # Enrollment
    enrollment_count = Column(Integer)
    
    # Dates
    study_start_date = Column(Date)
    primary_completion_date = Column(Date)
    completion_date = Column(Date)
    first_posted_date = Column(Date, index=True)
    results_first_posted_date = Column(Date)
    last_update_posted_date = Column(Date)
    
    # Results summary (if available)
    has_results = Column(Boolean, default=False)
    results_summary = Column(Text, nullable=True)
    primary_endpoint_met = Column(Boolean, nullable=True)
    
    # Raw data
    raw_data = Column(JSON)  # Full API response for reference
    
    # Metadata
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    last_synced_at = Column(DateTime)
    
    # Relationships
    company = relationship("Company", back_populates="trials")
    events = relationship("TrialEvent", back_populates="trial", lazy="dynamic")
    
    __table_args__ = (
        Index("idx_trial_phase_status", "phase", "overall_status"),
        Index("idx_trial_therapeutic_area", "therapeutic_area"),
    )
    
    def __repr__(self):
        return f"<Trial({self.nct_id}: {self.brief_title[:50]}...)>"


class TrialEvent(Base):
    """Events related to clinical trials (status changes, results, etc.)."""
    __tablename__ = "trial_events"
    
    id = Column(Integer, primary_key=True)
    trial_id = Column(Integer, ForeignKey("trials.id"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    
    event_type = Column(Enum(EventType), nullable=False, index=True)
    event_date = Column(Date, nullable=False, index=True)
    detected_at = Column(DateTime, server_default=func.now())
    
    # Event details
    previous_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=True)
    description = Column(Text)
    
    # Impact assessment
    expected_impact = Column(String(20))  # high, medium, low
    sentiment = Column(String(20))  # positive, negative, neutral
    
    # Raw data
    raw_data = Column(JSON)
    
    # Processing status
    processed = Column(Boolean, default=False)
    processed_at = Column(DateTime)
    
    # Relationships
    trial = relationship("Trial", back_populates="events")
    signal = relationship("Signal", back_populates="event", uselist=False)
    
    __table_args__ = (
        Index("idx_event_type_date", "event_type", "event_date"),
        Index("idx_event_company", "company_id", "event_date"),
    )
    
    def __repr__(self):
        return f"<TrialEvent({self.event_type.value}: {self.trial.nct_id})>"


class StockPrice(Base):
    """Daily stock price data."""
    __tablename__ = "stock_prices"
    
    id = Column(Integer, primary_key=True)
    ticker = Column(String(20), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    
    # OHLCV
    open_price = Column(Numeric(12, 4))
    high_price = Column(Numeric(12, 4))
    low_price = Column(Numeric(12, 4))
    close_price = Column(Numeric(12, 4))
    adj_close = Column(Numeric(12, 4))
    volume = Column(BigInteger)
    
    # Additional metrics
    market_cap = Column(Numeric(20, 2))
    
    # Metadata
    created_at = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uix_stock_price"),
        Index("idx_stock_price_ticker_date", "ticker", "date"),
    )


class Signal(Base):
    """Generated trading signals."""
    __tablename__ = "signals"
    
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("trial_events.id"), unique=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    
    # Signal details
    signal_type = Column(Enum(SignalType), nullable=False)
    confidence = Column(Numeric(4, 2), nullable=False)  # 0.00 to 1.00
    
    # Price targets
    entry_price = Column(Numeric(12, 4))
    target_price = Column(Numeric(12, 4))
    stop_loss = Column(Numeric(12, 4))
    
    # Position sizing
    position_size_pct = Column(Numeric(4, 2))  # % of portfolio
    max_position_value = Column(Numeric(15, 2))
    
    # Analysis breakdown
    catalyst_score = Column(Numeric(4, 2))
    company_score = Column(Numeric(4, 2))
    market_score = Column(Numeric(4, 2))
    timing_score = Column(Numeric(4, 2))
    
    # Reasoning
    reasoning = Column(Text)
    decision_factors = Column(JSON)
    
    # Timing
    generated_at = Column(DateTime, server_default=func.now())
    valid_until = Column(DateTime)
    
    # Status
    status = Column(String(20), default="active")  # active, executed, expired, cancelled
    
    # Relationships
    event = relationship("TrialEvent", back_populates="signal")
    company = relationship("Company", back_populates="signals")
    trade = relationship("Trade", back_populates="signal", uselist=False)
    
    def __repr__(self):
        return f"<Signal({self.signal_type.value}: {self.company.ticker} @ {self.confidence})>"


class Trade(Base):
    """Executed trades."""
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True)
    signal_id = Column(Integer, ForeignKey("signals.id"), unique=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    
    # Trade details
    direction = Column(String(10), nullable=False)  # LONG, SHORT
    entry_price = Column(Numeric(12, 4), nullable=False)
    entry_date = Column(DateTime, nullable=False)
    entry_shares = Column(Numeric(15, 4))
    entry_value = Column(Numeric(15, 2))
    
    # Exit details
    exit_price = Column(Numeric(12, 4))
    exit_date = Column(DateTime)
    exit_value = Column(Numeric(15, 2))
    exit_reason = Column(Enum(ExitReason))
    
    # Performance
    realized_pnl = Column(Numeric(15, 2))
    realized_pnl_pct = Column(Numeric(8, 4))
    holding_period_days = Column(Integer)
    
    # Attribution
    catalyst_type = Column(String(50))
    catalyst_description = Column(Text)
    expected_return = Column(Numeric(8, 4))
    prediction_error = Column(Numeric(8, 4))
    was_prediction_correct = Column(Boolean)
    
    # Risk management
    max_drawdown_pct = Column(Numeric(8, 4))
    max_profit_pct = Column(Numeric(8, 4))
    
    # Status
    status = Column(Enum(TradeStatus), default=TradeStatus.PENDING)
    
    # Metadata
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    signal = relationship("Signal", back_populates="trade")
    company = relationship("Company", back_populates="trades")
    
    def __repr__(self):
        return f"<Trade({self.company.ticker}: {self.status.value})>"


class EventStudy(Base):
    """Event study analysis results."""
    __tablename__ = "event_studies"
    
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("trial_events.id"))
    ticker = Column(String(20), nullable=False)
    
    # Event window returns
    car_1day = Column(Numeric(8, 4))  # Cumulative abnormal return
    car_3day = Column(Numeric(8, 4))
    car_5day = Column(Numeric(8, 4))
    car_10day = Column(Numeric(8, 4))
    
    # Statistical significance
    t_stat = Column(Numeric(8, 4))
    p_value = Column(Numeric(8, 4))
    is_significant = Column(Boolean)
    
    # Model parameters
    alpha = Column(Numeric(10, 6))
    beta = Column(Numeric(10, 6))
    r_squared = Column(Numeric(6, 4))
    
    # Raw data
    abnormal_returns = Column(JSON)
    
    # Metadata
    computed_at = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        Index("idx_event_study_event", "event_id"),
        Index("idx_event_study_ticker", "ticker"),
    )


class PerformanceMetrics(Base):
    """Aggregated performance metrics over time."""
    __tablename__ = "performance_metrics"
    
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    
    # Portfolio metrics
    portfolio_value = Column(Numeric(15, 2))
    cash_balance = Column(Numeric(15, 2))
    invested_value = Column(Numeric(15, 2))
    
    # Return metrics
    daily_return = Column(Numeric(8, 4))
    cumulative_return = Column(Numeric(10, 4))
    
    # Risk metrics
    volatility = Column(Numeric(8, 4))
    max_drawdown = Column(Numeric(8, 4))
    sharpe_ratio = Column(Numeric(8, 4))
    sortino_ratio = Column(Numeric(8, 4))
    
    # Trade statistics
    total_trades = Column(Integer)
    winning_trades = Column(Integer)
    losing_trades = Column(Integer)
    win_rate = Column(Numeric(5, 2))
    avg_win = Column(Numeric(8, 4))
    avg_loss = Column(Numeric(8, 4))
    profit_factor = Column(Numeric(8, 4))
    
    # Created at
    created_at = Column(DateTime, server_default=func.now())


class SystemLog(Base):
    """System activity logs."""
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, server_default=func.now(), index=True)
    level = Column(String(20), index=True)  # INFO, WARNING, ERROR, CRITICAL
    component = Column(String(50))  # Which module
    message = Column(Text)
    details = Column(JSON)  # Additional structured data


# Indexes for common queries
Index("idx_trial_event_company_date", TrialEvent.company_id, TrialEvent.event_date)
Index("idx_signal_confidence", Signal.confidence)
Index("idx_signal_status", Signal.status)
Index("idx_trade_status", Trade.status)
Index("idx_trade_entry_date", Trade.entry_date)
