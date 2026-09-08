"""Isolated counterfactual replay for frozen Forex PAPER strategies."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from typing import Any, Iterable

from app.trading.forex_candidate_v2 import ForexRegimeCandidatePolicy
from app.trading.forex_historical import (
    BidirectionalForexHistoricalBacktester,
    FixedForexCrossoverSignalGenerator,
    ForexHistoricalPolicy,
    ForexHistoricalSignal,
)
from app.trading.models import MarketBar, TradingValidationError


class ForexStrategyCounterfactualReplay:
    """Compare V1 and frozen V2 on independent, in-memory PAPER accounts."""

    MINIMUM_M15_BARS = 211

    def __init__(self, policy: ForexHistoricalPolicy | None = None) -> None:
        self.policy = policy or ForexHistoricalPolicy()
        self.candidate = ForexRegimeCandidatePolicy()

    def run(self, values: Iterable[MarketBar]) -> dict[str, Any]:
        bars = tuple(values)
        self._validate_m15(bars)
        generator = FixedForexCrossoverSignalGenerator(self.policy)
        v1_signals = generator.generate(bars)
        v2_signals, exclusions = self._v2_signals(bars, v1_signals)
        v1 = BidirectionalForexHistoricalBacktester(self.policy).run(
            bars, v1_signals
        )
        v2 = BidirectionalForexHistoricalBacktester(self.policy).run(
            bars, v2_signals
        )
        manifest = self._manifest(bars)
        return {
            "status": "FOREX_COUNTERFACTUAL_REPLAY_COMPLETED",
            "mode": "LOCAL_HISTORICAL_RESEARCH_ONLY",
            "manifest": manifest,
            "v1": v1,
            "v2": v2,
            "v1_signal_ids": [item.signal_id for item in v1_signals],
            "v2_signal_ids": [item.signal_id for item in v2_signals],
            "v2_exclusions": exclusions,
            "counterfactual_v2_portfolio_simulated": True,
            "portfolio_states_isolated": True,
            "closed_m15_bars_only": True,
            "same_bar_execution_blocked": True,
            "future_bar_access": False,
            "synthetic_cost_model": True,
            "results_comparable_within_pair_only": True,
            "cross_pair_aggregation_performed": False,
            "performance_validated": False,
            "automatic_paper_strategy_change": False,
            "broker_connection_used": False,
            "network_access": False,
            "paper_orders_sent": False,
            "live_orders_sent": False,
            "real_money_access": False,
        }

    def _v2_signals(
        self,
        bars: tuple[MarketBar, ...],
        signals: tuple[ForexHistoricalSignal, ...],
    ) -> tuple[tuple[ForexHistoricalSignal, ...], dict[str, int]]:
        index_by_time = {bar.timestamp: index for index, bar in enumerate(bars)}
        retained: list[ForexHistoricalSignal] = []
        exclusions: dict[str, int] = {}
        for signal in signals:
            prefix = bars[:index_by_time[signal.timestamp] + 1]
            code = self._v2_exclusion(prefix, signal)
            if code:
                exclusions[code] = exclusions.get(code, 0) + 1
            else:
                retained.append(signal)
        return tuple(retained), dict(sorted(exclusions.items()))

    def _v2_exclusion(
        self,
        prefix: tuple[MarketBar, ...],
        signal: ForexHistoricalSignal,
    ) -> str:
        if len(prefix) < self.candidate.required_m15_bar_count:
            return "CANDIDATE_V2_H1_HISTORY_INSUFFICIENT"
        closes = self._complete_h1_closes(prefix)
        if len(closes) < self.candidate.h1_slow_window:
            return "CANDIDATE_V2_H1_HISTORY_INSUFFICIENT"
        fast = self._mean(closes[-self.candidate.h1_fast_window:])
        slow = self._mean(closes[-self.candidate.h1_slow_window:])
        aligned = (
            signal.action == "OPEN_LONG" and fast > slow and closes[-1] > slow
        ) or (
            signal.action == "OPEN_SHORT" and fast < slow and closes[-1] < slow
        )
        return "" if aligned else "CANDIDATE_V2_H1_REGIME_NOT_ALIGNED"

    @staticmethod
    def _complete_h1_closes(
        bars: tuple[MarketBar, ...],
    ) -> tuple[Decimal, ...]:
        grouped: dict[datetime, list[MarketBar]] = {}
        for bar in bars:
            hour = bar.timestamp.replace(minute=0, second=0, microsecond=0)
            grouped.setdefault(hour, []).append(bar)
        return tuple(
            group[-1].close
            for hour in sorted(grouped)
            if (group := grouped[hour])
            and tuple(item.timestamp.minute for item in group) == (0, 15, 30, 45)
        )

    def _manifest(self, bars: tuple[MarketBar, ...]) -> dict[str, Any]:
        rows = [{
            "symbol": bar.symbol,
            "timestamp": bar.timestamp.isoformat(),
            "open": str(bar.open),
            "high": str(bar.high),
            "low": str(bar.low),
            "close": str(bar.close),
            "volume": str(bar.volume),
            "currency": bar.currency,
        } for bar in bars]
        policy = {key: str(value) for key, value in asdict(self.policy).items()}
        return {
            "schema_version": 1,
            "bar_count": len(bars),
            "data_sha256": self._hash(rows),
            "v1_policy_sha256": self._hash(policy),
            "v2_candidate_id": self.candidate.candidate_id,
            "v2_policy_sha256": self.candidate.fingerprint_sha256,
            "assumed_spread_pips": str(self.policy.assumed_spread_pips),
            "assumed_slippage_pips": str(self.policy.assumed_slippage_pips),
        }

    @classmethod
    def _validate_m15(cls, bars: tuple[MarketBar, ...]) -> None:
        if len(bars) < cls.MINIMUM_M15_BARS:
            raise TradingValidationError("forex_replay: insufficient_m15_bars")
        if any(not isinstance(bar, MarketBar) for bar in bars):
            raise TradingValidationError("forex_replay: market_bar_required")
        if any(not cls._valid_m15_gap(left, right) for left, right in zip(
            bars, bars[1:]
        )):
            raise TradingValidationError("forex_replay: invalid_m15_cadence")

    @staticmethod
    def _valid_m15_gap(left: MarketBar, right: MarketBar) -> bool:
        seconds = (right.timestamp - left.timestamp).total_seconds()
        aligned = all(
            value.second == 0
            and value.microsecond == 0
            and value.minute in {0, 15, 30, 45}
            for value in (left.timestamp, right.timestamp)
        )
        if not aligned:
            return False
        if seconds == 900:
            return True
        return bool(
            left.timestamp.weekday() == 4
            and right.timestamp.weekday() == 6
            and 36 * 3600 <= seconds <= 60 * 3600
            and seconds % 900 == 0
        )

    @staticmethod
    def _mean(values: tuple[Decimal, ...]) -> Decimal:
        return sum(values, Decimal("0")) / Decimal(len(values))

    @staticmethod
    def _hash(value: object) -> str:
        payload = json.dumps(
            value, sort_keys=True, ensure_ascii=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


__all__ = ["ForexStrategyCounterfactualReplay"]
