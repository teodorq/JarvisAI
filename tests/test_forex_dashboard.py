from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from app.trading.forex_dashboard import ForexPaperDashboard


class _Executor:
    def __init__(self, value: dict) -> None:
        self.value = value

    def status(self) -> dict:
        return dict(self.value)


def _account() -> dict:
    return {
        "mode": "FOREX_PAPER_ONLY",
        "live_trading_enabled": False,
        "network_access": False,
        "balance_pln": "100000.00",
        "equity_pln": "99998.12",
        "unrealized_pnl_pln": "-1.88",
        "realized_pnl_pln": "0",
        "position_count": 1,
        "open_positions": [{
            "pair": "USD_CHF",
            "side": "SHORT",
            "units": "2714",
            "entry_price": "0.799040",
            "current_price": "0.799040",
            "stop_loss": "0.800040",
            "take_profit": "0.797040",
            "opened_at": "2026-08-21T10:09:38+00:00",
        }],
        "closed_trade_count": 0,
        "performance": {
            "status": "COLLECTING_PAPER_SAMPLE",
            "metric_scope": "CURRENT_SAMPLE_CONTRACT",
            "valid_closed_trade_count": 1,
            "all_time_closed_trade_count": 2,
            "minimum_closed_trades_for_review": 20,
            "sample_progress_pct": "5.00",
            "average_trade_pnl_pln": "-44.26",
            "profit_factor": "0.0000",
            "maximum_closed_trade_drawdown_pln": "44.26",
            "maximum_closed_trade_drawdown_pct": "0.04",
            "maximum_consecutive_losses": 1,
            "pair_breakdown": {
                "USD_CHF": {
                    "closed_trade_count": 1,
                    "sample_contract_closed_trade_count": 1,
                    "all_time_closed_trade_count": 2,
                    "winning_trade_count": 0,
                    "losing_trade_count": 1,
                    "win_rate_pct": "0.00",
                    "net_realized_pnl_pln": "-44.26",
                    "all_time_net_realized_pnl_pln": "-85.88",
                    "average_trade_pnl_pln": "-44.26",
                    "profit_factor": "0.0000",
                    "minimum_closed_trades_for_review": 20,
                    "remaining_closed_trades_for_review": 19,
                    "sample_progress_pct": "5.00",
                    "review_status": "COLLECTING_PAIR_SAMPLE",
                },
            },
            "integrity": {"evidence_valid": True},
            "sample_contract_review": {
                "status": "TRACKING_CURRENT_CONTRACT",
                "contract_tracking_enabled": True,
                "expected_contract_id": "FOREX_PAPER_V1_20260831",
                "expected_fingerprint_sha256": "a" * 64,
                "current_contract_closed_trade_count": 1,
                "legacy_unversioned_closed_trade_count": 1,
                "foreign_contract_closed_trade_count": 0,
                "all_time_closed_trade_count": 2,
                "sample_contract_consistent": True,
            },
            "all_time_summary": {
                "closed_trade_count": 2,
                "winning_trade_count": 0,
                "losing_trade_count": 2,
                "win_rate_pct": "0.00",
                "net_realized_pnl_pln": "-85.88",
                "average_trade_pnl_pln": "-42.94",
                "profit_factor": "0.0000",
                "maximum_closed_trade_drawdown_pln": "85.88",
                "maximum_closed_trade_drawdown_pct": "0.09",
                "maximum_consecutive_losses": 2,
            },
            "trade_diagnostics": {
                "status": "COMPLETE",
                "closed_trade_count": 1,
                "holding_time_observed_count": 1,
                "holding_time_missing_count": 0,
                "average_holding_minutes": "45.00",
                "median_holding_minutes": "45.00",
                "shortest_holding_minutes": "45.00",
                "longest_holding_minutes": "45.00",
                "exit_reason_counts": {
                    "stop_loss": 0,
                    "take_profit": 1,
                    "strategy": 0,
                    "unspecified": 0,
                },
                "holding_time_coverage_complete": True,
                "exit_reason_coverage_complete": True,
                "diagnostics_complete": True,
            },
        },
        "processed_cycle_count": 75,
        "audit_chain_valid": True,
        "kill_switch_active": False,
        "loss_streak_safety": {
            "active": True,
            "code": "CONSECUTIVE_LOSS_COOLDOWN",
            "current_consecutive_losses": 3,
            "threshold": 3,
            "cooldown_minutes": 360,
            "resume_at": "2026-08-21T16:09:38+00:00",
            "remaining_seconds": 10800,
            "paper_only": True,
        },
        "weekly_loss_safety": {
            "active": False,
            "code": "READY",
            "weekly_pnl_pln": "-44.26",
            "loss_limit_pln": "2000.00",
            "remaining_loss_capacity_pln": "1955.74",
            "maximum_loss_pct": "2.00",
            "week_start_at": "2026-08-17T00:00:00+00:00",
            "reset_at": "2026-08-24T00:00:00+00:00",
            "closed_trade_count": 1,
            "paper_only": True,
        },
        "weekly_loss_safety": {
            "active": False,
            "code": "READY",
            "weekly_pnl_pln": "-44.26",
            "loss_limit_pln": "2000.00",
            "remaining_loss_capacity_pln": "1955.74",
            "maximum_loss_pct": "2.00",
            "week_start_at": "2026-08-17T00:00:00+00:00",
            "reset_at": "2026-08-24T00:00:00+00:00",
            "closed_trade_count": 1,
            "paper_only": True,
        },
    }


def _write_result(root: Path, account: dict, *, live: bool = False) -> None:
    path = root / "data" / "trading" / "forex_paper_last.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "status": "PAPER_CYCLE_COMPLETED",
        "observed_at": "2026-08-21T10:09:38+00:00",
        "broker_orders_sent": False,
        "live_orders_sent": live,
        "real_money_access": False,
        "paper": {
            "mode": "FOREX_PAPER_ONLY",
            "live_orders_sent": False,
            "network_access": False,
            "account": account,
        },
    }), encoding="utf-8")


def _write_safe_block(
    root: Path,
    *,
    live: bool = False,
    observation: dict | None = None,
) -> None:
    path = root / "data" / "trading" / "forex_paper_last.json"
    path.parent.mkdir(parents=True)
    payload = {
        "status": "PAPER_CYCLE_BLOCKED",
        "reason": "CURRENT_OBSERVATION_BLOCKED",
        "observed_at": "2026-08-31T18:54:00+00:00",
        "broker_orders_sent": False,
        "live_orders_sent": live,
        "real_money_access": False,
    }
    if observation is not None:
        payload["observation"] = observation
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_observer_status(
    root: Path,
    *,
    failures: int = 0,
    attention: bool = False,
    live: bool = False,
    checked_at: datetime | None = None,
    recovery_gap_seconds: int = 0,
    recovery_detected_at: datetime | None = None,
    replay_exit_count: int = 0,
    replay_ambiguous_count: int = 0,
    replay_at: datetime | None = None,
) -> None:
    path = root / "data" / "trading" / "forex_observer_status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema_version": 1,
        "status": "WAITING_NEXT_CYCLE",
        "checked_at": (checked_at or datetime.now(timezone.utc)).isoformat(),
        "market_window_open": True,
        "mt5_running": True,
        "protection_interval_seconds": 60,
        "protection_status": (
            "PAPER_PROTECTION_BLOCKED"
            if failures
            else "NO_PROTECTION_TRIGGER"
        ),
        "protection_checked_at": datetime.now(timezone.utc).isoformat(),
        "protection_reason": "MT5_PROTECTION_DATA_STALE" if failures else "",
        "protection_consecutive_failure_count": failures,
        "protection_attention_required": attention,
        "previous_protection_check_restored": True,
        "last_recovery_gap_seconds": recovery_gap_seconds,
        "last_recovery_gap_detected_at": (
            recovery_detected_at.isoformat() if recovery_detected_at else ""
        ),
        "last_recovery_replay_status": (
            "RECOVERY_REPLAY_APPLIED" if replay_exit_count else ""
        ),
        "last_recovery_replay_at": replay_at.isoformat() if replay_at else "",
        "last_recovery_replay_exit_count": replay_exit_count,
        "last_recovery_replay_ambiguous_count": replay_ambiguous_count,
        "broker_orders_sent": False,
        "live_orders_sent": live,
        "real_money_access": False,
    }), encoding="utf-8")


def test_dashboard_projects_latest_safe_paper_cycle() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        _write_result(root, _account())
        dashboard = ForexPaperDashboard(root, executor=_Executor({}))

        snapshot = dashboard.snapshot()

        assert snapshot["status"] == "READY"
        assert snapshot["position_count"] == 1
        assert snapshot["positions"][0] == {
            "pair": "USD_CHF",
            "side": "SHORT",
            "units": "2714",
            "entry_price": "0.799040",
            "current_price": "0.799040",
            "stop_loss": "0.800040",
            "take_profit": "0.797040",
            "opened_at": "2026-08-21T10:09:38+00:00",
        }
        assert snapshot["unrealized_pnl_pln"] == "-1.88"
        assert snapshot["performance"]["valid_closed_trade_count"] == 1
        assert snapshot["performance"]["profit_factor"] == "0.0000"
        assert snapshot["performance"]["evidence_valid"] is True
        assert snapshot["performance"]["live_promotion_ready"] is False
        pair = snapshot["performance"]["pair_breakdown"]["USD_CHF"]
        assert pair["closed_trade_count"] == 1
        assert pair["all_time_closed_trade_count"] == 2
        assert pair["net_realized_pnl_pln"] == "-44.26"
        assert pair["all_time_net_realized_pnl_pln"] == "-85.88"
        assert pair["profit_factor"] == "0.0000"
        assert pair["performance_validated"] is False
        assert pair["review_status"] == "COLLECTING_PAIR_SAMPLE"
        assert pair["sample_progress_pct"] == "5.00"
        assert snapshot["performance"]["pair_review"]["ready_pair_count"] == 0
        assert snapshot["performance"]["pair_review"]["collecting_pairs"] == [
            "USD_CHF"
        ]
        assert snapshot["performance"]["pair_review"]["unobserved_pair_count"] == 6
        assert snapshot["performance"]["pair_review"]["automatic_pair_disable"] is False
        contract = snapshot["performance"]["sample_contract_review"]
        assert contract["contract_tracking_enabled"] is True
        assert contract["current_contract_closed_trade_count"] == 1
        assert contract["legacy_unversioned_closed_trade_count"] == 1
        assert contract["automatic_sample_merge"] is False
        assert snapshot["performance"]["all_time_summary"] == {
            "closed_trade_count": 2,
            "winning_trade_count": 0,
            "losing_trade_count": 2,
            "win_rate_pct": "0.00",
            "net_realized_pnl_pln": "-85.88",
            "average_trade_pnl_pln": "-42.94",
            "profit_factor": "0.0000",
            "maximum_closed_trade_drawdown_pln": "85.88",
            "maximum_closed_trade_drawdown_pct": "0.09",
            "maximum_consecutive_losses": 2,
        }
        diagnostics = snapshot["performance"]["trade_diagnostics"]
        assert diagnostics["status"] == "COMPLETE"
        assert diagnostics["average_holding_minutes"] == "45.00"
        assert diagnostics["exit_reason_counts"] == {
            "stop_loss": 0,
            "take_profit": 1,
            "strategy": 0,
            "unspecified": 0,
        }
        assert diagnostics["diagnostics_complete"] is True
        assert snapshot["new_entries_paused_by_loss_streak"] is True
        assert snapshot["new_entries_paused_by_weekly_loss"] is False
        assert snapshot["weekly_loss_safety"] == {
            "active": False,
            "code": "READY",
            "weekly_pnl_pln": "-44.26",
            "loss_limit_pln": "2000.00",
            "remaining_loss_capacity_pln": "1955.74",
            "maximum_loss_pct": "2.00",
            "week_start_at": "2026-08-17T00:00:00+00:00",
            "reset_at": "2026-08-24T00:00:00+00:00",
            "closed_trade_count": 1,
            "paper_only": True,
        }
        assert snapshot["new_entries_paused_by_weekly_loss"] is False
        assert snapshot["weekly_loss_safety"] == {
            "active": False,
            "code": "READY",
            "weekly_pnl_pln": "-44.26",
            "loss_limit_pln": "2000.00",
            "remaining_loss_capacity_pln": "1955.74",
            "maximum_loss_pct": "2.00",
            "week_start_at": "2026-08-17T00:00:00+00:00",
            "reset_at": "2026-08-24T00:00:00+00:00",
            "closed_trade_count": 1,
            "paper_only": True,
        }
        assert snapshot["loss_streak_safety"] == {
            "active": True,
            "code": "CONSECUTIVE_LOSS_COOLDOWN",
            "current_consecutive_losses": 3,
            "threshold": 3,
            "cooldown_minutes": 360,
            "resume_at": "2026-08-21T16:09:38+00:00",
            "remaining_seconds": 10800,
            "paper_only": True,
        }
        assert "wstrzymane" in snapshot["message"]
        assert snapshot["live_orders_sent"] is False


def test_dashboard_prioritizes_weekly_loss_pause_message() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        account = _account()
        account["loss_streak_safety"]["active"] = False
        account["weekly_loss_safety"]["active"] = True
        account["weekly_loss_safety"]["code"] = "WEEKLY_LOSS_LIMIT"
        _write_result(root, account)

        snapshot = ForexPaperDashboard(
            root,
            executor=_Executor({}),
        ).snapshot()

        assert snapshot["new_entries_paused_by_weekly_loss"] is True
        assert "tygodniowy limit straty" in snapshot["message"]


def test_dashboard_prioritizes_weekly_loss_pause_message() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        account = _account()
        account["loss_streak_safety"]["active"] = False
        account["weekly_loss_safety"]["active"] = True
        account["weekly_loss_safety"]["code"] = "WEEKLY_LOSS_LIMIT"
        _write_result(root, account)

        snapshot = ForexPaperDashboard(
            root,
            executor=_Executor({}),
        ).snapshot()

        assert snapshot["new_entries_paused_by_weekly_loss"] is True
        assert "tygodniowy limit straty" in snapshot["message"]


def test_dashboard_projects_position_protection_attention_safely() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        _write_result(root, _account())
        _write_observer_status(root, failures=3, attention=True)

        snapshot = ForexPaperDashboard(
            root,
            executor=_Executor({}),
        ).snapshot()

        protection = snapshot["position_protection"]
        assert protection["available"] is True
        assert protection["status"] == "PAPER_PROTECTION_BLOCKED"
        assert protection["interval_seconds"] == 60
        assert protection["consecutive_failure_count"] == 3
        assert protection["attention_required"] is True
        assert protection["live_orders_sent"] is False
        assert "wymaga uwagi" in snapshot["message"]


def test_dashboard_sanitizes_an_unsafe_observer_heartbeat() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        _write_result(root, _account())
        _write_observer_status(root, live=True)

        snapshot = ForexPaperDashboard(
            root,
            executor=_Executor({}),
        ).snapshot()

        protection = snapshot["position_protection"]
        assert protection["status"] == "SAFETY_VIOLATION"
        assert protection["attention_required"] is True
        assert protection["live_orders_sent"] is False
        assert snapshot["live_orders_sent"] is False


def test_dashboard_marks_a_future_observer_heartbeat_as_stale() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        _write_result(root, _account())
        _write_observer_status(
            root,
            checked_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )

        snapshot = ForexPaperDashboard(
            root,
            executor=_Executor({}),
        ).snapshot()

        protection = snapshot["position_protection"]
        assert protection["available"] is True
        assert protection["stale"] is True
        assert protection["live_orders_sent"] is False


def test_dashboard_projects_recent_restart_recovery_gap() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        _write_result(root, _account())
        _write_observer_status(
            root,
            recovery_gap_seconds=77_100,
            recovery_detected_at=datetime.now(timezone.utc),
        )

        protection = ForexPaperDashboard(
            root,
            executor=_Executor({}),
        ).snapshot()["position_protection"]

        assert protection["previous_check_restored"] is True
        assert protection["last_recovery_gap_seconds"] == 77_100
        assert protection["last_recovery_gap_detected_at"]
        assert protection["recent_recovery"] is True
        assert protection["live_orders_sent"] is False


def test_dashboard_projects_recent_m1_recovery_replay() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        _write_result(root, _account())
        _write_observer_status(
            root,
            replay_exit_count=1,
            replay_ambiguous_count=1,
            replay_at=datetime.now(timezone.utc),
        )

        protection = ForexPaperDashboard(
            root,
            executor=_Executor({}),
        ).snapshot()["position_protection"]

        assert protection["last_recovery_replay_status"] == (
            "RECOVERY_REPLAY_APPLIED"
        )
        assert protection["last_recovery_replay_exit_count"] == 1
        assert protection["last_recovery_replay_ambiguous_count"] == 1
        assert protection["recent_recovery_replay"] is True
        assert protection["real_money_access"] is False


def test_dashboard_blocks_result_that_claims_live_execution() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        _write_result(root, _account(), live=True)
        dashboard = ForexPaperDashboard(root, executor=_Executor(_account()))

        snapshot = dashboard.snapshot()

        assert snapshot["status"] == "BLOCKED"
        assert snapshot["positions"] == []
        assert snapshot["live_orders_sent"] is False


def test_dashboard_uses_safe_local_ledger_when_result_is_missing() -> None:
    with TemporaryDirectory() as temporary:
        dashboard = ForexPaperDashboard(
            Path(temporary), executor=_Executor(_account())
        )

        snapshot = dashboard.snapshot()

        assert snapshot["status"] == "READY"
        assert snapshot["source"] == "LOCAL_PAPER_LEDGER"
        assert snapshot["position_count"] == 1


def test_dashboard_rebuilds_metrics_from_ledger_after_report_upgrade() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        stale_account = _account()
        stale_account["performance"].pop("metric_scope")
        _write_result(root, stale_account)
        dashboard = ForexPaperDashboard(root, executor=_Executor(_account()))

        snapshot = dashboard.snapshot()

        assert snapshot["status"] == "READY"
        assert snapshot["source"] == "LOCAL_PAPER_LEDGER_AFTER_REPORT_UPGRADE"
        assert snapshot["performance"]["metric_scope"] == (
            "CURRENT_SAMPLE_CONTRACT"
        )


def test_dashboard_uses_ledger_after_safe_block_without_account() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        _write_safe_block(root)
        dashboard = ForexPaperDashboard(root, executor=_Executor(_account()))

        snapshot = dashboard.snapshot()

        assert snapshot["status"] == "READY"
        assert snapshot["source"] == "LOCAL_PAPER_LEDGER_AFTER_SAFE_BLOCK"
        assert snapshot["observed_at"] == "2026-08-31T18:54:00+00:00"
        assert snapshot["performance"]["sample_contract_review"][
            "contract_tracking_enabled"
        ] is True


def test_dashboard_explains_a_safe_macro_entry_block() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        _write_safe_block(root, observation={
            "opening_blocks": ["HIGH_IMPACT_EVENT_WINDOW"],
            "opening_blocks_by_pair": {
                "EUR_USD": ["HIGH_IMPACT_EVENT_WINDOW"],
                "USD_JPY": ["HIGH_IMPACT_EVENT_WINDOW"],
                "NOT_A_PAIR": ["HIGH_IMPACT_EVENT_WINDOW"],
            },
        })
        dashboard = ForexPaperDashboard(root, executor=_Executor(_account()))

        snapshot = dashboard.snapshot()

        assert snapshot["status"] == "READY"
        assert snapshot["entry_block"] == {
            "active": True,
            "codes": ["HIGH_IMPACT_EVENT_WINDOW"],
            "pairs": ["EUR_USD", "USD_JPY"],
            "paper_only": True,
        }
        assert "ważne wydarzenie makro" in snapshot["message"]
        assert "EUR/USD, USD/JPY" in snapshot["message"]
        assert "NOT/A/PAIR" not in snapshot["message"]
        assert snapshot["live_orders_sent"] is False


def test_dashboard_does_not_fallback_after_block_claiming_live() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        _write_safe_block(root, live=True)
        dashboard = ForexPaperDashboard(root, executor=_Executor(_account()))

        snapshot = dashboard.snapshot()

        assert snapshot["status"] == "BLOCKED"
        assert snapshot["live_orders_sent"] is False


def test_dashboard_drops_invalid_positions_and_numbers() -> None:
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        account = _account()
        account["equity_pln"] = "NaN"
        account["balance_pln"] = "1e999999"
        account["open_positions"] = [{"pair": "BAD", "side": "BUY"}]
        _write_result(root, account)

        snapshot = ForexPaperDashboard(root, executor=_Executor({})).snapshot()

        assert snapshot["equity_pln"] == "0.00"
        assert snapshot["balance_pln"] == "0.00"
        assert snapshot["positions"] == []
        assert snapshot["position_count"] == 0
