"""Broker-neutral, local-only paper-trading foundation for JARVIS OS."""

from app.trading.backtest import HistoricalPaperBacktester
from app.trading.control_center import TradingControlCenter
from app.trading.dataset import HistoricalCsvLoader, HistoricalDataset
from app.trading.forex_coordinator import ForexPaperCoordinator, ForexPaperInstruction
from app.trading.forex_activity import ForexPaperActivityFeed
from app.trading.forex_activity_journal import ForexPaperActivityJournal
from app.trading.forex_dashboard import ForexPaperDashboard
from app.trading.forex_candidate_v2 import (
    ForexRegimeCandidatePolicy,
    ForexRegimeFilteredScanner,
)
from app.trading.forex_autopilot import ForexPaperAutopilot
from app.trading.forex_executor import ForexPaperExecutionEngine
from app.trading.forex_historical import (
    BidirectionalForexHistoricalBacktester,
    FixedForexCrossoverSignalGenerator,
    ForexHistoricalPolicy,
    ForexHistoricalSignal,
    ForexHistoricalWalkForwardValidator,
    ForexWalkForwardPolicy,
)
from app.trading.forex_ledger import ForexPaperLedger
from app.trading.forex_paper_performance import (
    ForexPaperPerformancePolicy,
    build_forex_paper_performance_review,
)
from app.trading.forex_portfolio_historical import (
    ForexPortfolioHistoricalBacktester,
    ForexPortfolioHistoricalPolicy,
    ForexPortfolioHistoricalWalkForwardValidator,
    ForexPortfolioWalkForwardPolicy,
)
from app.trading.forex_models import (
    ForexBar,
    ForexPair,
    ForexPosition,
    ForexQuote,
    ForexSafetyContext,
    MAJOR_FOREX_PAIRS,
    USD_PLN_CONVERSION_PAIR,
    major_pair,
)
from app.trading.forex_risk import (
    ForexPaperPolicy,
    ForexPortfolioRiskEngine,
    ForexRateBook,
    ForexRiskDecision,
)
from app.trading.forex_research_status import ForexHistoricalResearchGate
from app.trading.forex_scanner import (
    ForexMarketScanner,
    ForexPairAssessment,
    ForexScannerPolicy,
)
from app.trading.forex_sample_contract import (
    CONTRACT_ID as FOREX_PAPER_SAMPLE_CONTRACT_ID,
    build_forex_paper_sample_contract,
    is_superseded_sample_contract,
    sample_contracts_match,
    verify_forex_paper_sample_contract,
)
from app.trading.forex_strategy_cohorts import (
    ForexStrategyCohortReview,
    build_forex_strategy_cohort_review,
)
from app.trading.forex_strategy_replay import ForexStrategyCounterfactualReplay
from app.trading.forex_trade_diagnostics import (
    build_forex_trade_diagnostics,
)
from app.trading.ledger import PaperTradingLedger
from app.trading.models import (
    MarketBar,
    MarketQuote,
    PaperOrder,
    StrategySignal,
    TradingValidationError,
)
from app.trading.paper_broker import LiveTradingBlockedError, PaperTradingEngine
from app.trading.policy import PaperTradingPolicy
from app.trading.risk import PreTradeRiskEngine, RiskDecision
from app.trading.walk_forward import (
    ChronologicalHoldoutValidator,
    HistoricalWalkForwardValidator,
    WalkForwardPolicy,
)

__all__ = [
    "HistoricalPaperBacktester",
    "BidirectionalForexHistoricalBacktester",
    "ChronologicalHoldoutValidator",
    "HistoricalWalkForwardValidator",
    "HistoricalCsvLoader",
    "HistoricalDataset",
    "ForexBar",
    "FixedForexCrossoverSignalGenerator",
    "ForexHistoricalPolicy",
    "ForexHistoricalSignal",
    "ForexHistoricalWalkForwardValidator",
    "ForexHistoricalResearchGate",
    "ForexMarketScanner",
    "ForexPair",
    "ForexPairAssessment",
    "ForexPaperCoordinator",
    "ForexPaperActivityFeed",
    "ForexPaperActivityJournal",
    "ForexPaperDashboard",
    "ForexPaperAutopilot",
    "ForexPaperExecutionEngine",
    "ForexPaperInstruction",
    "ForexPaperLedger",
    "ForexPaperPolicy",
    "ForexPaperPerformancePolicy",
    "ForexPortfolioRiskEngine",
    "ForexPortfolioHistoricalBacktester",
    "ForexPortfolioHistoricalPolicy",
    "ForexPortfolioHistoricalWalkForwardValidator",
    "ForexPortfolioWalkForwardPolicy",
    "ForexPosition",
    "ForexQuote",
    "ForexRateBook",
    "ForexRegimeCandidatePolicy",
    "ForexRegimeFilteredScanner",
    "ForexRiskDecision",
    "ForexSafetyContext",
    "ForexScannerPolicy",
    "FOREX_PAPER_SAMPLE_CONTRACT_ID",
    "ForexStrategyCohortReview",
    "ForexWalkForwardPolicy",
    "LiveTradingBlockedError",
    "MarketBar",
    "MarketQuote",
    "MAJOR_FOREX_PAIRS",
    "PaperOrder",
    "PaperTradingEngine",
    "PaperTradingLedger",
    "PaperTradingPolicy",
    "PreTradeRiskEngine",
    "RiskDecision",
    "StrategySignal",
    "TradingControlCenter",
    "TradingValidationError",
    "USD_PLN_CONVERSION_PAIR",
    "major_pair",
    "build_forex_paper_performance_review",
    "build_forex_paper_sample_contract",
    "is_superseded_sample_contract",
    "build_forex_strategy_cohort_review",
    "ForexStrategyCounterfactualReplay",
    "build_forex_trade_diagnostics",
    "sample_contracts_match",
    "verify_forex_paper_sample_contract",
    "WalkForwardPolicy",
]
