from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.trading.forex_strategy_replay import ForexStrategyCounterfactualReplay
from app.trading.models import MarketBar, TradingValidationError


def _bars(count: int = 280) -> tuple[MarketBar, ...]:
    start = datetime(2026, 1, 5, tzinfo=timezone.utc)
    pattern = tuple(Decimal(value) for value in ("0", "1", "2", "3", "4", "3", "2", "1"))
    result = []
    for index in range(count):
        close = Decimal("1.1000") + pattern[index % len(pattern)] / Decimal("1000")
        result.append(MarketBar.create(
            symbol="EUR_USD",
            timestamp=start + timedelta(minutes=15 * index),
            open=close,
            high=close + Decimal("0.0005"),
            low=close - Decimal("0.0005"),
            close=close,
            volume="100",
            currency="USD",
        ))
    return tuple(result)


def test_replay_uses_isolated_costed_next_bar_portfolios() -> None:
    result = ForexStrategyCounterfactualReplay().run(_bars())

    assert result["status"] == "FOREX_COUNTERFACTUAL_REPLAY_COMPLETED"
    assert result["counterfactual_v2_portfolio_simulated"] is True
    assert result["portfolio_states_isolated"] is True
    assert result["v1"] is not result["v2"]
    assert set(result["v2_signal_ids"]).issubset(result["v1_signal_ids"])
    assert len(result["manifest"]["data_sha256"]) == 64
    assert len(result["manifest"]["v1_policy_sha256"]) == 64
    assert result["manifest"]["v2_candidate_id"] == "FOREX_REGIME_V2_20260820"
    assert result["same_bar_execution_blocked"] is True
    assert result["synthetic_cost_model"] is True
    assert result["results_comparable_within_pair_only"] is True
    assert result["cross_pair_aggregation_performed"] is False
    assert result["performance_validated"] is False
    assert result["broker_connection_used"] is False
    assert result["network_access"] is False
    assert result["live_orders_sent"] is False


def test_future_bars_do_not_change_earlier_v2_decisions() -> None:
    replay = ForexStrategyCounterfactualReplay()
    complete = _bars(300)
    prefix = complete[:260]

    early = replay.run(prefix)
    later = replay.run(complete)

    cutoff = prefix[-1].timestamp.strftime("%Y%m%dT%H%M%S")
    later_early_ids = [
        signal_id for signal_id in later["v2_signal_ids"]
        if signal_id.split("-")[-2] <= cutoff
    ]
    assert later_early_ids == early["v2_signal_ids"]
    assert later["manifest"]["data_sha256"] != early["manifest"]["data_sha256"]


def test_replay_fails_closed_on_short_or_broken_m15_history() -> None:
    replay = ForexStrategyCounterfactualReplay()
    with pytest.raises(TradingValidationError, match="insufficient_m15_bars"):
        replay.run(_bars(210))

    broken = list(_bars())
    broken[220] = MarketBar.create(
        symbol="EUR_USD",
        timestamp=broken[219].timestamp,
        open="1.1", high="1.2", low="1.0", close="1.1",
        volume="100", currency="USD",
    )
    with pytest.raises(TradingValidationError, match="invalid_m15_cadence"):
        replay.run(broken)


def test_replay_accepts_only_a_bounded_friday_to_sunday_market_gap() -> None:
    source = list(_bars())
    shift_from = 200
    friday = datetime(2026, 1, 9, 20, 45, tzinfo=timezone.utc)
    offset = friday - source[shift_from - 1].timestamp
    for index, bar in enumerate(source):
        timestamp = bar.timestamp + offset
        if index >= shift_from:
            timestamp += timedelta(hours=48, minutes=15)
        source[index] = MarketBar.create(
            symbol=bar.symbol, timestamp=timestamp, open=bar.open,
            high=bar.high, low=bar.low, close=bar.close,
            volume=bar.volume, currency=bar.currency,
        )

    result = ForexStrategyCounterfactualReplay().run(source)

    assert result["closed_m15_bars_only"] is True
