"""Analysis package."""

from .signal_generator import SignalGenerator, get_signal_generator, TradingSignal
from .event_study import EventStudyAnalyzer, get_event_study_analyzer

__all__ = [
    "SignalGenerator",
    "get_signal_generator",
    "TradingSignal",
    "EventStudyAnalyzer",
    "get_event_study_analyzer",
]
