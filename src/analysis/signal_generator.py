"""Advanced signal generation with ML-based prediction."""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import joblib
from loguru import logger

from src.utils.config import settings
from src.database.models import (
    TrialEvent, EventType, SignalType, Signal, Company
)
from src.data_sources.company_mapper import get_company_mapper, CompanyMapping
from src.data_sources.market_data import get_market_data_client
from src.analysis.technical import get_technical_analysis, TechnicalSignal
from src.analysis.risk_manager import get_risk_manager, ATRData


@dataclass
class SignalScore:
    """Component scores for a signal."""
    catalyst_score: float
    company_score: float
    market_score: float
    timing_score: float
    ml_score: float
    ta_score: float = 0.5  # Technical analysis score
    
    @property
    def weighted_total(self) -> float:
        """Calculate weighted total score.
        Catalyst (30%) + TA (25%) + Company (20%) + Market (10%) + Timing (10%) + ML (5%)
        """
        return (
            self.catalyst_score * 0.30 +
            self.ta_score * 0.25 +
            self.company_score * 0.20 +
            self.market_score * 0.10 +
            self.timing_score * 0.10 +
            self.ml_score * 0.05
        )


@dataclass
class TradingSignal:
    """Generated trading signal."""
    ticker: str
    signal_type: SignalType
    confidence: float
    entry_price: Decimal
    target_price: Decimal
    stop_loss: Decimal
    position_size_pct: float
    scores: SignalScore
    reasoning: str
    decision_factors: Dict[str, Any]
    event: TrialEvent
    ta: Optional['TechnicalSignal'] = None  # Technical analysis data


class SignalGenerator:
    """Generate trading signals from trial events."""
    
    # Event type impact scores
    EVENT_IMPACT = {
        EventType.RESULTS_POSTED: 1.0,
        EventType.FDA_APPROVAL: 1.0,
        EventType.TRIAL_TERMINATED: 0.9,
        EventType.PHASE_ADVANCE: 0.8,
        EventType.PRIMARY_COMPLETION: 0.6,
        EventType.ENROLLMENT_COMPLETE: 0.4,
        EventType.NEW_TRIAL: 0.3,
        EventType.PROTOCOL_AMENDMENT: 0.2,
        EventType.TRIAL_SUSPENDED: 0.7,
    }
    
    # Phase impact multipliers
    PHASE_MULTIPLIERS = {
        "PHASE1": 0.5,
        "PHASE2": 0.7,
        "PHASE3": 1.0,
        "PHASE4": 0.4,
        None: 0.3,
    }
    
    # Therapeutic area impact
    THERAPEUTIC_IMPACT = {
        "oncology": 1.0,
        "cancer": 1.0,
        "rare disease": 0.9,
        "orphan": 0.9,
        "neurology": 0.8,
        "cns": 0.8,
        "immunology": 0.7,
        "infectious disease": 0.7,
        "cardiovascular": 0.6,
        "metabolic": 0.6,
        "respiratory": 0.5,
        "gastroenterology": 0.5,
    }
    
    def __init__(self):
        self.market_client = get_market_data_client()
        self.company_mapper = get_company_mapper()
        self.risk_manager = get_risk_manager()
        self._ml_model = None
        self._scaler = StandardScaler()
        self._load_ml_model()
    
    def _load_ml_model(self):
        """Load pre-trained ML model if available."""
        try:
            model_path = "data/models/signal_predictor.pkl"
            self._ml_model = joblib.load(model_path)
            logger.info("Loaded ML model from disk")
        except FileNotFoundError:
            logger.info("No pre-trained ML model found, using rule-based scoring")
            self._ml_model = None
    
    async def _get_market_cap(self, ticker: str) -> Optional[float]:
        """Get market cap for a ticker via yfinance."""
        try:
            import yfinance as yf
            loop = asyncio.get_event_loop()
            stock = yf.Ticker(ticker)
            info = await loop.run_in_executor(None, lambda: stock.fast_info)
            mcap = getattr(info, 'market_cap', None)
            return float(mcap) if mcap else None
        except Exception as e:
            logger.debug(f"Could not get market cap for {ticker}: {e}")
            return None

    async def generate_signal(
        self,
        event: TrialEvent,
        company: Company
    ) -> Optional[TradingSignal]:
        """Generate trading signal for a trial event."""
        try:
            # [IMPROVEMENT 2] Minimum market cap filter ($20B)
            market_cap = await self._get_market_cap(company.ticker)
            if market_cap is not None and market_cap < settings.MIN_MARKET_CAP:
                logger.info(f"Skipping {company.ticker}: market cap ${market_cap/1e9:.1f}B < ${settings.MIN_MARKET_CAP/1e9:.0f}B minimum")
                return None

            # Get current price
            current_price = await self.market_client.get_current_price(company.ticker)
            if not current_price:
                logger.warning(f"Could not get price for {company.ticker}")
                return None
            
            # Calculate component scores
            catalyst_score = await self._score_catalyst(event, company)
            company_score = await self._score_company(company)
            market_score = await self._score_market_conditions(company)
            timing_score = await self._score_timing(event, company)
            ml_score = await self._ml_prediction(event, company)
            
            # Technical analysis
            ta_result = await get_technical_analysis(company.ticker, days=90)
            ta_score = ta_result.ta_score if ta_result else 0.5
            
            scores = SignalScore(
                catalyst_score=catalyst_score,
                company_score=company_score,
                market_score=market_score,
                timing_score=timing_score,
                ml_score=ml_score,
                ta_score=ta_score
            )
            
            # Calculate overall confidence
            confidence = scores.weighted_total
            
            # Check minimum confidence threshold
            if confidence < settings.MIN_CONFIDENCE:
                logger.debug(f"Confidence {confidence:.2f} below threshold for {company.ticker}")
                return None
            
            # Determine signal type
            signal_type = self._determine_signal_type(event, confidence)
            
            # [IMPROVEMENT 3] Don't trade against TA — if TA says SELL, downgrade BUY to HOLD
            if signal_type in [SignalType.BUY, SignalType.STRONG_BUY] and ta_result:
                ta_bearish = (
                    (ta_result.rsi_14 is not None and ta_result.rsi_14 > 70) or
                    ta_result.macd_crossover == "bearish_cross" or
                    ta_result.macd_trend == "bearish"
                )
                if ta_bearish:
                    logger.info(f"Downgrading {company.ticker} from {signal_type.value} to HOLD — TA bearish (RSI={ta_result.rsi_14}, MACD={ta_result.macd_trend})")
                    signal_type = SignalType.HOLD
            
            # [V2] Volume confirmation - downgrade signal if volume is weak
            vol_confirmed, vol_ratio = await self.risk_manager.confirm_volume(company.ticker)
            if not vol_confirmed and signal_type in [SignalType.STRONG_BUY, SignalType.BUY]:
                logger.info(f"Weak volume for {company.ticker} (ratio={vol_ratio}), downgrading signal")
                if signal_type == SignalType.STRONG_BUY:
                    signal_type = SignalType.BUY
                else:
                    signal_type = SignalType.HOLD
            
            # [V2] Circuit breaker check
            if self.risk_manager._circuit_breaker_active:
                logger.warning(f"Circuit breaker active — suppressing signal for {company.ticker}")
                return None
            
            # [V2] ATR-based price targets and position sizing
            atr_data = await self.risk_manager.calculate_atr(company.ticker)
            
            target_price, stop_loss = self._calculate_targets(
                current_price, signal_type, confidence, event, atr_data
            )
            
            # [V2] Volatility-adjusted position sizing
            portfolio_value = getattr(settings, 'INITIAL_CAPITAL', 100000)
            position_size, stop_dist = await self.risk_manager.calculate_position_size(
                company.ticker, confidence, portfolio_value
            )
            
            # Generate reasoning
            reasoning = self._generate_reasoning(event, scores, company)
            
            # Decision factors
            ta_factors = {}
            if ta_result:
                ta_factors = {
                    "rsi_14": ta_result.rsi_14,
                    "rsi_zone": ta_result.rsi_zone,
                    "macd_crossover": ta_result.macd_crossover,
                    "macd_trend": ta_result.macd_trend,
                    "volume_ratio": ta_result.volume_ratio,
                    "volume_surge": ta_result.volume_surge,
                    "rsi_divergence": ta_result.rsi_divergence,
                    "macd_divergence": ta_result.macd_divergence,
                    "ta_verdict": ta_result.ta_verdict,
                    "ta_reasons": ta_result.ta_reasons,
                }
            
            decision_factors = {
                "event_type": event.event_type.value,
                "phase": event.trial.phase if event.trial else None,
                "therapeutic_area": event.trial.therapeutic_area if event.trial else None,
                "market_cap_bucket": company.market_cap_bucket,
                "catalyst_breakdown": {
                    "event_impact": self.EVENT_IMPACT.get(event.event_type, 0.5),
                    "phase_multiplier": self.PHASE_MULTIPLIERS.get(
                        event.trial.phase if event.trial else None, 0.5
                    ),
                },
                "scores": {
                    "catalyst": round(catalyst_score, 2),
                    "technical": round(ta_score, 2),
                    "company": round(company_score, 2),
                    "market": round(market_score, 2),
                    "timing": round(timing_score, 2),
                    "ml": round(ml_score, 2),
                },
                "technical_analysis": ta_factors,
            }
            
            return TradingSignal(
                ticker=company.ticker,
                signal_type=signal_type,
                confidence=confidence,
                entry_price=current_price,
                target_price=target_price,
                stop_loss=stop_loss,
                position_size_pct=position_size,
                scores=scores,
                reasoning=reasoning,
                decision_factors=decision_factors,
                event=event,
                ta=ta_result,
            )
            
        except Exception as e:
            logger.error(f"Error generating signal for {company.ticker}: {e}")
            return None
    
    async def _score_catalyst(self, event: TrialEvent, company: Company) -> float:
        """Score the quality of the catalyst."""
        score = 0.5
        
        # Event type impact
        event_impact = self.EVENT_IMPACT.get(event.event_type, 0.5)
        score = event_impact
        
        # Phase multiplier
        if event.trial and event.trial.phase:
            phase_mult = self.PHASE_MULTIPLIERS.get(event.trial.phase, 0.5)
            score *= phase_mult
        
        # Therapeutic area
        if event.trial and event.trial.therapeutic_area:
            area = event.trial.therapeutic_area.lower()
            for key, impact in self.THERAPEUTIC_IMPACT.items():
                if key in area:
                    score *= impact
                    break
        
        # Results quality (if applicable)
        if event.event_type == EventType.RESULTS_POSTED:
            if event.trial and event.trial.primary_endpoint_met is not None:
                if event.trial.primary_endpoint_met:
                    score *= 1.2
                else:
                    score *= 0.3  # Negative results
        
        # Trial design quality
        if event.trial:
            design_score = self._score_trial_design(event.trial)
            score *= design_score
        
        return min(score, 1.0)
    
    def _score_trial_design(self, trial) -> float:
        """Score trial design quality."""
        score = 1.0
        
        # Randomization
        if trial.allocation and "randomized" in trial.allocation.lower():
            score *= 1.1
        
        # Blinding
        if trial.masking and "double" in trial.masking.lower():
            score *= 1.1
        
        # Enrollment size
        if trial.enrollment_count:
            if trial.enrollment_count >= 1000:
                score *= 1.15
            elif trial.enrollment_count >= 300:
                score *= 1.1
            elif trial.enrollment_count >= 100:
                score *= 1.05
        
        return min(score, 1.3)
    
    async def _score_company(self, company: Company) -> float:
        """Score company strength and readiness."""
        score = 0.5
        
        # Market cap bucket
        if company.market_cap_bucket == "large":
            score += 0.2
        elif company.market_cap_bucket == "mid":
            score += 0.1
        elif company.market_cap_bucket == "small":
            score += 0.0
        else:
            score -= 0.1
        
        # Pipeline concentration (lower is better - more focused)
        if company.pipeline_concentration is not None:
            if company.pipeline_concentration > 0.7:
                score += 0.15  # High dependency = bigger moves
            elif company.pipeline_concentration > 0.4:
                score += 0.05
        
        # Number of active trials
        if company.num_active_trials:
            if company.num_active_trials >= 10:
                score += 0.1  # Diversified pipeline
            elif company.num_active_trials >= 3:
                score += 0.05
        
        # Financial health (cash position)
        if company.cash_and_equivalents and company.market_cap:
            cash_ratio = float(company.cash_and_equivalents) / float(company.market_cap)
            if cash_ratio > 0.2:
                score += 0.1  # Strong cash position
            elif cash_ratio > 0.1:
                score += 0.05
        
        return min(max(score, 0.0), 1.0)
    
    async def _score_market_conditions(self, company: Company) -> float:
        """Score current market conditions."""
        score = 0.5
        
        try:
            # Sector performance
            sector_perf = await self.market_client.get_sector_performance(period_days=30)
            xbi_return = sector_perf.get("XBI", 0)
            
            if xbi_return > 0.1:  # Strong sector
                score += 0.15
            elif xbi_return > 0.05:
                score += 0.1
            elif xbi_return > 0:
                score += 0.05
            elif xbi_return < -0.1:  # Weak sector
                score -= 0.1
            
            # Stock volatility
            volatility = await self.market_client.get_volatility(company.ticker, 30)
            if volatility:
                if volatility < 0.3:  # Low volatility
                    score += 0.05
                elif volatility > 0.8:  # Very high volatility
                    score -= 0.1
            
            # Liquidity check
            avg_volume = await self.market_client.get_average_volume(company.ticker, 30)
            if avg_volume:
                if avg_volume >= 1_000_000:
                    score += 0.1
                elif avg_volume < 100_000:
                    score -= 0.1
            
        except Exception as e:
            logger.debug(f"Error scoring market conditions: {e}")
        
        return min(max(score, 0.0), 1.0)
    
    async def _score_timing(self, event: TrialEvent, company: Company) -> float:
        """Score timing and information edge."""
        score = 0.5
        
        # Information freshness
        if event.detected_at:
            hours_since = (datetime.now() - event.detected_at).total_seconds() / 3600
            if hours_since < 1:
                score += 0.2  # Very fresh
            elif hours_since < 4:
                score += 0.1
            elif hours_since < 24:
                score += 0.05
            elif hours_since > 72:
                score -= 0.1  # Stale
        
        # Check for confounding events
        try:
            is_near_earnings, _ = await self.market_client.is_near_earnings(
                company.ticker, datetime.now(), 5
            )
            if is_near_earnings:
                score -= 0.15  # Risk of earnings confound
        except:
            pass
        
        # Price momentum (avoid chasing)
        try:
            prices = await self.market_client.get_price_history(
                company.ticker,
                datetime.now() - timedelta(days=5)
            )
            if len(prices) >= 2:
                recent_return = self.market_client.calculate_cumulative_return(prices, -2)
                if recent_return > 0.1:  # Already up 10%
                    score -= 0.1  # May have missed the move
                elif recent_return < -0.05:  # Down recently
                    score += 0.05  # Potential oversold bounce
        except:
            pass
        
        return min(max(score, 0.0), 1.0)
    
    async def _ml_prediction(self, event: TrialEvent, company: Company) -> float:
        """Get ML model prediction if available."""
        if self._ml_model is None or not settings.ENABLE_ML_PREDICTION:
            return 0.5
        
        try:
            # Create feature vector
            features = self._extract_features(event, company)
            
            # Scale features
            features_scaled = self._scaler.transform([features])
            
            # Predict probability of positive return
            prob = self._ml_model.predict_proba(features_scaled)[0][1]
            return prob
            
        except Exception as e:
            logger.debug(f"ML prediction failed: {e}")
            return 0.5
    
    def _extract_features(self, event: TrialEvent, company: Company) -> List[float]:
        """Extract features for ML prediction."""
        features = [
            # Event features
            self.EVENT_IMPACT.get(event.event_type, 0.5),
            self.PHASE_MULTIPLIERS.get(event.trial.phase if event.trial else None, 0.5),
            1.0 if event.trial and event.trial.has_results else 0.0,
            
            # Company features
            {"small": 0.0, "mid": 0.5, "large": 1.0}.get(company.market_cap_bucket, 0.5),
            float(company.pipeline_concentration or 0.5),
            min(company.num_active_trials or 0, 20) / 20.0,
            
            # Market features (placeholders - would be filled with real data)
            0.5,  # Sector momentum
            0.5,  # Volatility
            0.5,  # Liquidity
        ]
        
        return features
    
    def _determine_signal_type(self, event: TrialEvent, confidence: float) -> SignalType:
        """Determine signal type based on confidence and event."""
        # Negative events
        if event.event_type in [EventType.TRIAL_TERMINATED, EventType.TRIAL_SUSPENDED]:
            if confidence >= settings.STRONG_SELL_THRESHOLD:
                return SignalType.STRONG_SELL
            return SignalType.SELL
        
        # Positive events
        if confidence >= settings.STRONG_BUY_THRESHOLD:
            return SignalType.STRONG_BUY
        elif confidence >= settings.BUY_THRESHOLD:
            return SignalType.BUY
        else:
            return SignalType.HOLD
    
    def _calculate_targets(
        self,
        current_price: Decimal,
        signal_type: SignalType,
        confidence: float,
        event: TrialEvent,
        atr_data: 'Optional[ATRData]' = None,
    ) -> Tuple[Decimal, Decimal]:
        """Calculate price targets and stop loss using ATR when available.
        
        V2: ATR-based stops replace fixed percentage stops.
        Stop = entry - (ATR_14 * multiplier)
        Target = entry + (ATR_14 * target_multiplier)
        """
        price_f = float(current_price)
        
        if signal_type in [SignalType.STRONG_BUY, SignalType.BUY]:
            if atr_data and atr_data.atr_14 > 0:
                # ATR-based targets
                atr = atr_data.atr_14
                
                # Stop: 2x ATR below entry (adaptive to volatility)
                stop_mult = 2.0
                # Target: risk-reward based on event type
                if event.event_type == EventType.RESULTS_POSTED:
                    target_mult = 4.0  # 2:1 R:R minimum for high-impact
                elif event.event_type == EventType.FDA_APPROVAL:
                    target_mult = 5.0  # 2.5:1 R:R for FDA
                elif event.event_type == EventType.PHASE_ADVANCE:
                    target_mult = 3.0
                else:
                    target_mult = 2.5
                
                # Confidence bonus
                target_mult *= (1.0 + (confidence - 0.5) * 0.5)
                
                stop_loss = Decimal(str(round(price_f - atr * stop_mult, 2)))
                target_price = Decimal(str(round(price_f + atr * target_mult, 2)))
                
                # Floor: stop can't be more than 10% below entry
                min_stop = current_price * Decimal('0.90')
                stop_loss = max(stop_loss, min_stop)
                
            else:
                # Fallback: percentage-based
                base_target = 0.08
                base_stop = 0.04
                
                if event.event_type == EventType.RESULTS_POSTED:
                    base_target, base_stop = 0.12, 0.05
                elif event.event_type == EventType.FDA_APPROVAL:
                    base_target, base_stop = 0.15, 0.05
                
                target_mult = 1.0 + (confidence - 0.5)
                stop_mult = 1.0 - (confidence - 0.5) * 0.5
                
                target_price = current_price * Decimal(1 + base_target * target_mult)
                stop_loss = current_price * Decimal(1 - base_stop * stop_mult)
            
        elif signal_type in [SignalType.STRONG_SELL, SignalType.SELL]:
            if atr_data and atr_data.atr_14 > 0:
                atr = atr_data.atr_14
                stop_loss = Decimal(str(round(price_f + atr * 2.0, 2)))
                target_price = Decimal(str(round(price_f - atr * 3.0, 2)))
            else:
                target_price = current_price * Decimal('0.94')
                stop_loss = current_price * Decimal('1.05')
        else:
            target_price = current_price
            stop_loss = current_price
        
        return round(target_price, 2), round(stop_loss, 2)
    
    def _calculate_position_size(self, confidence: float, ticker: str) -> float:
        """Calculate position size based on confidence and risk.
        
        [IMPROVEMENT 5] Tiered position sizing:
          - 70%+ confidence = 4% position size
          - 68-70% confidence = 2% position size
          - Below 68% = minimal (fallback)
        """
        if confidence >= 0.70:
            position_size = 0.04
        elif confidence >= 0.68:
            position_size = 0.02
        else:
            position_size = 0.01  # Minimal for low confidence
        
        # Cap at max position size
        return min(position_size, settings.MAX_POSITION_SIZE_PCT)
    
    def _generate_reasoning(
        self,
        event: TrialEvent,
        scores: SignalScore,
        company: Company
    ) -> str:
        """Generate human-readable reasoning for the signal."""
        reasons = []
        
        # Event description
        event_desc = event.event_type.value.replace("_", " ").title()
        reasons.append(f"{event_desc} for {company.name}")
        
        if event.trial:
            if event.trial.phase:
                reasons.append(f"Phase: {event.trial.phase}")
            if event.trial.therapeutic_area:
                reasons.append(f"Therapeutic Area: {event.trial.therapeutic_area}")
        
        # Score breakdown
        reasons.append(f"\nScore Breakdown:")
        reasons.append(f"  • Catalyst Quality: {scores.catalyst_score:.0%}")
        reasons.append(f"  • Technical Analysis: {scores.ta_score:.0%}")
        reasons.append(f"  • Company Strength: {scores.company_score:.0%}")
        reasons.append(f"  • Market Conditions: {scores.market_score:.0%}")
        reasons.append(f"  • Timing Edge: {scores.timing_score:.0%}")
        if scores.ml_score != 0.5:
            reasons.append(f"  • ML Prediction: {scores.ml_score:.0%}")
        
        return "\n".join(reasons)


# Singleton instance
_generator: Optional[SignalGenerator] = None


def get_signal_generator() -> SignalGenerator:
    """Get singleton instance of SignalGenerator."""
    global _generator
    if _generator is None:
        _generator = SignalGenerator()
    return _generator
