"""Bounded, read-only projection of the local Forex PAPER account."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.core.project_paths import resolve_project_root
from app.trading.forex_entry_blocks import (
    dashboard_block_message,
    opening_block_details,
)


_MAJOR_PAIRS = (
    "EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF",
    "AUD_USD", "USD_CAD", "NZD_USD",
)
class ForexPaperDashboard:
    """Expose only safe account fields required by the owner dashboard."""

    MAX_RESULT_BYTES = 2_000_000

    def __init__(self, project_root: str | Path | None, *, executor: Any) -> None:
        root = resolve_project_root(project_root)
        self.result_path = root / "data" / "trading" / "forex_paper_last.json"
        self.observer_status_path = (
            root / "data" / "trading" / "forex_observer_status.json"
        )
        self.executor = executor

    def snapshot(self) -> dict[str, Any]:
        payload = self._load_result()
        if payload is not None:
            if self._result_is_paper_only(payload):
                paper = payload.get("paper")
                paper = dict(paper) if isinstance(paper, dict) else {}
                account = paper.get("account")
                account = dict(account) if isinstance(account, dict) else {}
                if not self._performance_scope_is_current(account):
                    return self._local_snapshot(
                        observed_at=str(payload.get("observed_at", "")),
                        source="LOCAL_PAPER_LEDGER_AFTER_REPORT_UPGRADE",
                    )
                return self._project(
                    account,
                    observed_at=str(payload.get("observed_at", "")),
                    source="LATEST_PAPER_CYCLE",
                )
            if self._safe_blocked_cycle_without_account(payload):
                snapshot = self._local_snapshot(
                    observed_at=str(payload.get("observed_at", "")),
                    source="LOCAL_PAPER_LEDGER_AFTER_SAFE_BLOCK",
                )
                return self._with_safe_entry_block(snapshot, payload)
            return self._blocked("Raport nie przeszedł kontroli PAPER ONLY.")
        return self._local_snapshot(
            observed_at="",
            source="LOCAL_PAPER_LEDGER",
        )

    @classmethod
    def _with_safe_entry_block(
        cls,
        snapshot: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if snapshot.get("status") != "READY":
            return snapshot
        codes, pairs = opening_block_details(payload)
        result = dict(snapshot)
        result["entry_block"] = {
            "active": True,
            "codes": list(codes),
            "pairs": list(pairs),
            "paper_only": True,
        }
        protection = result.get("position_protection")
        protection = dict(protection) if isinstance(protection, dict) else {}
        if protection.get("attention_required") is True:
            return result
        result["message"] = dashboard_block_message(codes, pairs)
        return result

    def _local_snapshot(self, *, observed_at: str, source: str) -> dict[str, Any]:
        try:
            account = self.executor.status()
        except Exception:
            return self._blocked("Lokalna księga PAPER jest chwilowo niedostępna.")
        account = dict(account) if isinstance(account, dict) else {}
        if not self._account_is_paper_only(account):
            return self._blocked("Lokalna księga nie potwierdza trybu PAPER ONLY.")
        return self._project(account, observed_at=observed_at, source=source)

    def _load_result(self) -> dict[str, Any] | None:
        try:
            size = self.result_path.stat().st_size
            if size <= 0 or size > self.MAX_RESULT_BYTES:
                return None
            value = json.loads(self.result_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        return dict(value) if isinstance(value, dict) else None

    @classmethod
    def _result_is_paper_only(cls, payload: dict[str, Any]) -> bool:
        paper = payload.get("paper")
        paper = dict(paper) if isinstance(paper, dict) else {}
        account = paper.get("account")
        account = dict(account) if isinstance(account, dict) else {}
        root_flags = all(
            payload.get(key) is False
            for key in ("broker_orders_sent", "live_orders_sent", "real_money_access")
        )
        paper_flags = (
            paper.get("live_orders_sent") is False
            and paper.get("network_access") is False
        )
        return root_flags and paper_flags and cls._account_is_paper_only(account)

    @staticmethod
    def _safe_blocked_cycle_without_account(payload: dict[str, Any]) -> bool:
        return bool(
            payload.get("status") == "PAPER_CYCLE_BLOCKED"
            and "paper" not in payload
            and all(
                payload.get(key) is False
                for key in (
                    "broker_orders_sent",
                    "live_orders_sent",
                    "real_money_access",
                )
            )
        )

    @staticmethod
    def _account_is_paper_only(account: dict[str, Any]) -> bool:
        return (
            str(account.get("mode", "")) == "FOREX_PAPER_ONLY"
            and account.get("live_trading_enabled") is False
            and account.get("network_access") is False
        )

    @staticmethod
    def _performance_scope_is_current(account: dict[str, Any]) -> bool:
        performance = account.get("performance")
        performance = (
            dict(performance) if isinstance(performance, dict) else {}
        )
        contract = performance.get("sample_contract_review")
        contract = dict(contract) if isinstance(contract, dict) else {}
        if contract.get("contract_tracking_enabled") is not True:
            return True
        return bool(
            performance.get("metric_scope") == "CURRENT_SAMPLE_CONTRACT"
            and isinstance(performance.get("all_time_summary"), dict)
        )

    def _project(
        self,
        account: dict[str, Any],
        *,
        observed_at: str,
        source: str,
    ) -> dict[str, Any]:
        positions = self._positions(account.get("open_positions"))
        performance = self._performance(account.get("performance"))
        loss_streak_safety = self._loss_streak_safety(
            account.get("loss_streak_safety")
        )
        weekly_loss_safety = self._weekly_loss_safety(
            account.get("weekly_loss_safety")
        )
        position_protection = self._position_protection()
        message = "Lokalna symulacja; brak zleceń u brokera."
        if position_protection["attention_required"]:
            message = (
                "Ochrona SL/TP wymaga uwagi; szczegóły są widoczne w historii. "
                "Zlecenia LIVE pozostają niedostępne."
            )
        elif weekly_loss_safety["active"]:
            message = (
                "Nowe wejścia PAPER są wstrzymane przez tygodniowy limit "
                "straty; zweryfikowane zamknięcia nadal działają."
            )
        elif loss_streak_safety["active"]:
            message = (
                "Nowe wejścia PAPER są wstrzymane po serii strat; "
                "zweryfikowane zamknięcia nadal działają."
            )
        return {
            "status": "READY",
            "mode": "FOREX_PAPER_ONLY",
            "source": source,
            "observed_at": " ".join(observed_at.split())[:64],
            "balance_pln": self._number(account.get("balance_pln"), 2),
            "equity_pln": self._number(account.get("equity_pln"), 2),
            "unrealized_pnl_pln": self._number(
                account.get("unrealized_pnl_pln"), 2
            ),
            "realized_pnl_pln": self._number(account.get("realized_pnl_pln"), 2),
            "position_count": len(positions),
            "positions": positions,
            "closed_trade_count": self._count(account.get("closed_trade_count")),
            "performance": performance,
            "processed_cycle_count": self._count(
                account.get("processed_cycle_count")
            ),
            "audit_chain_valid": account.get("audit_chain_valid") is True,
            "kill_switch_active": account.get("kill_switch_active") is True,
            "loss_streak_safety": loss_streak_safety,
            "weekly_loss_safety": weekly_loss_safety,
            "position_protection": position_protection,
            "new_entries_paused_by_loss_streak": loss_streak_safety["active"],
            "new_entries_paused_by_weekly_loss": weekly_loss_safety["active"],
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "real_money_access": False,
            "message": message,
        }

    def _position_protection(self) -> dict[str, Any]:
        empty = {
            "available": False,
            "status": "NO_HEARTBEAT",
            "checked_at": "",
            "reason": "",
            "interval_seconds": 0,
            "consecutive_failure_count": 0,
            "attention_required": False,
            "stale": True,
            "market_window_open": False,
            "mt5_running": False,
            "previous_check_restored": False,
            "last_recovery_gap_seconds": 0,
            "last_recovery_gap_detected_at": "",
            "recent_recovery": False,
            "last_recovery_replay_status": "",
            "last_recovery_replay_at": "",
            "last_recovery_replay_exit_count": 0,
            "last_recovery_replay_ambiguous_count": 0,
            "recent_recovery_replay": False,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "real_money_access": False,
        }
        try:
            size = self.observer_status_path.stat().st_size
            if size <= 0 or size > 65_536:
                return empty
            value = json.loads(
                self.observer_status_path.read_text(encoding="utf-8-sig")
            )
            payload = dict(value) if isinstance(value, dict) else {}
            if payload.get("schema_version") != 1:
                return empty
            checked_at = datetime.fromisoformat(
                str(payload.get("checked_at", "")).replace("Z", "+00:00")
            ).astimezone(timezone.utc)
            interval = max(
                0,
                min(300, int(payload.get("protection_interval_seconds", 0))),
            )
            failures = max(0, min(1_000, int(
                payload.get("protection_consecutive_failure_count", 0)
            )))
            recovery_gap = max(0, min(
                604_800,
                int(payload.get("last_recovery_gap_seconds", 0)),
            ))
            replay_exits = max(0, min(
                2,
                int(payload.get("last_recovery_replay_exit_count", 0)),
            ))
            replay_ambiguous = max(0, min(
                replay_exits,
                int(payload.get("last_recovery_replay_ambiguous_count", 0)),
            ))
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ):
            return empty
        market_open = payload.get("market_window_open") is True
        age = (datetime.now(timezone.utc) - checked_at).total_seconds()
        recovery_detected_at = ""
        recent_recovery = False
        try:
            raw_recovery_at = str(
                payload.get("last_recovery_gap_detected_at", "")
            )[:80]
            if raw_recovery_at:
                recovery_at = datetime.fromisoformat(
                    raw_recovery_at.replace("Z", "+00:00")
                ).astimezone(timezone.utc)
                recovery_detected_at = recovery_at.isoformat()
                recovery_age = (
                    datetime.now(timezone.utc) - recovery_at
                ).total_seconds()
                recent_recovery = bool(
                    recovery_gap > max(180, interval * 3)
                    and -5 <= recovery_age <= 20 * 60
                )
        except (TypeError, ValueError):
            recovery_detected_at = ""
            recent_recovery = False
        replay_status = str(
            payload.get("last_recovery_replay_status", "")
        )[:80]
        replay_at_text = ""
        recent_recovery_replay = False
        try:
            raw_replay_at = str(
                payload.get("last_recovery_replay_at", "")
            )[:80]
            if replay_status == "RECOVERY_REPLAY_APPLIED" and raw_replay_at:
                replay_at = datetime.fromisoformat(
                    raw_replay_at.replace("Z", "+00:00")
                ).astimezone(timezone.utc)
                replay_at_text = replay_at.isoformat()
                replay_age = (
                    datetime.now(timezone.utc) - replay_at
                ).total_seconds()
                recent_recovery_replay = bool(
                    replay_exits > 0 and -5 <= replay_age <= 20 * 60
                )
        except (TypeError, ValueError):
            replay_at_text = ""
            recent_recovery_replay = False
        unsafe = any(
            payload.get(key) is not False
            for key in (
                "broker_orders_sent",
                "live_orders_sent",
                "real_money_access",
            )
        )
        return {
            "available": True,
            "status": (
                "SAFETY_VIOLATION"
                if unsafe
                else str(payload.get("protection_status", "NOT_RUN"))[:80]
            ),
            "checked_at": checked_at.isoformat(),
            "reason": " ".join(
                str(payload.get("protection_reason", "")).split()
            )[:160],
            "interval_seconds": interval,
            "consecutive_failure_count": failures,
            "attention_required": bool(
                unsafe
                or payload.get("protection_attention_required") is True
                or failures >= 3
            ),
            "stale": bool(
                age < -5 or age > (180 if market_open else 20 * 60)
            ),
            "market_window_open": market_open,
            "mt5_running": payload.get("mt5_running") is True,
            "previous_check_restored": (
                payload.get("previous_protection_check_restored") is True
            ),
            "last_recovery_gap_seconds": recovery_gap,
            "last_recovery_gap_detected_at": recovery_detected_at,
            "recent_recovery": recent_recovery,
            "last_recovery_replay_status": replay_status,
            "last_recovery_replay_at": replay_at_text,
            "last_recovery_replay_exit_count": replay_exits,
            "last_recovery_replay_ambiguous_count": replay_ambiguous,
            "recent_recovery_replay": recent_recovery_replay,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "real_money_access": False,
        }

    @classmethod
    def _loss_streak_safety(cls, value: object) -> dict[str, Any]:
        item = dict(value) if isinstance(value, dict) else {}
        code = str(item.get("code", "READY")).strip().upper()
        if code not in {
            "READY",
            "CONSECUTIVE_LOSS_COOLDOWN",
            "COOLDOWN_COMPLETE",
            "INVALID_LOSS_TIMESTAMP",
        }:
            code = "UNKNOWN"
        return {
            "active": item.get("active") is True,
            "code": code,
            "current_consecutive_losses": cls._count(
                item.get("current_consecutive_losses")
            ),
            "threshold": cls._count(item.get("threshold") or 3),
            "cooldown_minutes": cls._count(
                item.get("cooldown_minutes") or 360
            ),
            "resume_at": " ".join(
                str(item.get("resume_at", "")).split()
            )[:64],
            "remaining_seconds": cls._count(
                item.get("remaining_seconds")
            ),
            "paper_only": True,
        }

    @classmethod
    def _weekly_loss_safety(cls, value: object) -> dict[str, Any]:
        item = dict(value) if isinstance(value, dict) else {}
        code = str(item.get("code", "READY")).strip().upper()
        if code not in {
            "READY",
            "WEEKLY_LOSS_LIMIT",
            "INVALID_ACCOUNT_BALANCE",
            "AUDIT_CHAIN_INVALID",
            "EXECUTION_AUDIT_MISMATCH",
            "INVALID_WEEKLY_HISTORY",
        }:
            code = "UNKNOWN"
        return {
            "active": item.get("active") is True,
            "code": code,
            "weekly_pnl_pln": cls._number(
                item.get("weekly_pnl_pln"), 2
            ),
            "loss_limit_pln": cls._number(
                item.get("loss_limit_pln"), 2
            ),
            "remaining_loss_capacity_pln": cls._number(
                item.get("remaining_loss_capacity_pln"), 2
            ),
            "maximum_loss_pct": cls._number(
                item.get("maximum_loss_pct"), 2
            ),
            "week_start_at": " ".join(
                str(item.get("week_start_at", "")).split()
            )[:64],
            "reset_at": " ".join(
                str(item.get("reset_at", "")).split()
            )[:64],
            "closed_trade_count": cls._count(
                item.get("closed_trade_count")
            ),
            "paper_only": True,
        }

    @classmethod
    def _performance(cls, value: object) -> dict[str, Any]:
        item = dict(value) if isinstance(value, dict) else {}
        integrity = item.get("integrity")
        integrity = dict(integrity) if isinstance(integrity, dict) else {}
        raw_factor = item.get("profit_factor")
        raw_pairs = item.get("pair_breakdown")
        raw_pairs = dict(raw_pairs) if isinstance(raw_pairs, dict) else {}
        pairs: dict[str, dict[str, Any]] = {}
        required = max(1, cls._count(
            item.get("minimum_closed_trades_for_review") or 20
        ))
        evidence_valid = integrity.get("evidence_valid") is True
        for pair in _MAJOR_PAIRS:
            raw_metrics = raw_pairs.get(pair)
            metrics = dict(raw_metrics) if isinstance(raw_metrics, dict) else {}
            pair_factor = metrics.get("profit_factor")
            count = cls._count(metrics.get("closed_trade_count"))
            sample_count = cls._count(
                metrics.get("sample_contract_closed_trade_count", count)
            )
            review_status = str(metrics.get("review_status", "")).upper()
            allowed_statuses = {
                "NO_CLOSED_TRADES",
                "COLLECTING_PAIR_SAMPLE",
                "READY_FOR_MANUAL_REVIEW",
                "BLOCKED_INVALID_EVIDENCE",
            }
            if not evidence_valid:
                review_status = "BLOCKED_INVALID_EVIDENCE"
            elif review_status not in allowed_statuses:
                review_status = (
                    "NO_CLOSED_TRADES" if count == 0 else "COLLECTING_PAIR_SAMPLE"
                )
            pairs[pair] = {
                "closed_trade_count": count,
                "sample_contract_closed_trade_count": sample_count,
                "all_time_closed_trade_count": cls._count(
                    metrics.get("all_time_closed_trade_count", count)
                ),
                "winning_trade_count": cls._count(
                    metrics.get("winning_trade_count")
                ),
                "losing_trade_count": cls._count(
                    metrics.get("losing_trade_count")
                ),
                "win_rate_pct": cls._number(
                    metrics.get("win_rate_pct"), 2
                ),
                "net_realized_pnl_pln": cls._number(
                    metrics.get("net_realized_pnl_pln"), 2
                ),
                "all_time_net_realized_pnl_pln": cls._number(
                    metrics.get(
                        "all_time_net_realized_pnl_pln",
                        metrics.get("net_realized_pnl_pln"),
                    ),
                    2,
                ),
                "average_trade_pnl_pln": cls._number(
                    metrics.get("average_trade_pnl_pln"), 2
                ),
                "profit_factor": (
                    cls._number(pair_factor, 4)
                    if pair_factor is not None
                    else None
                ),
                "minimum_closed_trades_for_review": required,
                "remaining_closed_trades_for_review": max(
                    0, required - sample_count
                ),
                "sample_progress_pct": cls._number(
                    min(100, sample_count * 100 / max(1, required)), 2
                ),
                "sample_size_sufficient_for_review": (
                    review_status == "READY_FOR_MANUAL_REVIEW"
                ),
                "review_status": review_status,
                "performance_validated": False,
                "automatic_pair_selection": False,
            }
        pair_review = cls._pair_review(pairs, required, evidence_valid)
        contract_review = cls._sample_contract_review(
            item.get("sample_contract_review")
        )
        all_time_summary = cls._metric_summary(item.get("all_time_summary"))
        trade_diagnostics = cls._trade_diagnostics(
            item.get("trade_diagnostics")
        )
        return {
            "status": str(item.get("status", "COLLECTING_PAPER_SAMPLE"))[:80],
            "metric_scope": (
                "CURRENT_SAMPLE_CONTRACT"
                if item.get("metric_scope") == "CURRENT_SAMPLE_CONTRACT"
                else "UNVERIFIED"
            ),
            "valid_closed_trade_count": cls._count(
                item.get("valid_closed_trade_count")
            ),
            "all_time_closed_trade_count": cls._count(
                item.get("all_time_closed_trade_count")
            ),
            "minimum_closed_trades_for_review": cls._count(
                item.get("minimum_closed_trades_for_review") or 20
            ),
            "sample_progress_pct": cls._number(
                item.get("sample_progress_pct"), 2
            ),
            "average_trade_pnl_pln": cls._number(
                item.get("average_trade_pnl_pln"), 2
            ),
            "profit_factor": (
                cls._number(raw_factor, 4)
                if raw_factor is not None
                else None
            ),
            "maximum_closed_trade_drawdown_pln": cls._number(
                item.get("maximum_closed_trade_drawdown_pln"), 2
            ),
            "maximum_closed_trade_drawdown_pct": cls._number(
                item.get("maximum_closed_trade_drawdown_pct"), 2
            ),
            "maximum_consecutive_losses": cls._count(
                item.get("maximum_consecutive_losses")
            ),
            "pair_breakdown": pairs,
            "pair_review": pair_review,
            "sample_contract_review": contract_review,
            "all_time_summary": all_time_summary,
            "trade_diagnostics": trade_diagnostics,
            "evidence_valid": evidence_valid,
            "performance_validated": False,
            "live_promotion_ready": False,
        }

    @classmethod
    def _trade_diagnostics(cls, value: object) -> dict[str, Any]:
        item = dict(value) if isinstance(value, dict) else {}
        raw_reasons = item.get("exit_reason_counts")
        reasons = dict(raw_reasons) if isinstance(raw_reasons, dict) else {}

        def optional_minutes(key: str) -> str | None:
            raw = item.get(key)
            return cls._number(raw, 2) if raw is not None else None

        return {
            "status": str(item.get("status", "NO_CLOSED_TRADES"))[:40],
            "mode": "FOREX_PAPER_TRADE_DIAGNOSTICS_READ_ONLY",
            "closed_trade_count": cls._count(item.get("closed_trade_count")),
            "holding_time_observed_count": cls._count(
                item.get("holding_time_observed_count")
            ),
            "holding_time_missing_count": cls._count(
                item.get("holding_time_missing_count")
            ),
            "average_holding_minutes": optional_minutes(
                "average_holding_minutes"
            ),
            "median_holding_minutes": optional_minutes(
                "median_holding_minutes"
            ),
            "shortest_holding_minutes": optional_minutes(
                "shortest_holding_minutes"
            ),
            "longest_holding_minutes": optional_minutes(
                "longest_holding_minutes"
            ),
            "exit_reason_counts": {
                key: cls._count(reasons.get(key))
                for key in (
                    "stop_loss",
                    "take_profit",
                    "strategy",
                    "unspecified",
                )
            },
            "holding_time_coverage_complete": (
                item.get("holding_time_coverage_complete") is True
            ),
            "exit_reason_coverage_complete": (
                item.get("exit_reason_coverage_complete") is True
            ),
            "diagnostics_complete": item.get("diagnostics_complete") is True,
            "performance_validated": False,
            "automatic_strategy_change": False,
            "live_promotion_ready": False,
        }

    @classmethod
    def _metric_summary(cls, value: object) -> dict[str, Any]:
        item = dict(value) if isinstance(value, dict) else {}
        factor = item.get("profit_factor")
        return {
            "closed_trade_count": cls._count(item.get("closed_trade_count")),
            "winning_trade_count": cls._count(item.get("winning_trade_count")),
            "losing_trade_count": cls._count(item.get("losing_trade_count")),
            "win_rate_pct": cls._number(item.get("win_rate_pct"), 2),
            "net_realized_pnl_pln": cls._number(
                item.get("net_realized_pnl_pln"), 2
            ),
            "average_trade_pnl_pln": cls._number(
                item.get("average_trade_pnl_pln"), 2
            ),
            "profit_factor": (
                cls._number(factor, 4) if factor is not None else None
            ),
            "maximum_closed_trade_drawdown_pln": cls._number(
                item.get("maximum_closed_trade_drawdown_pln"), 2
            ),
            "maximum_closed_trade_drawdown_pct": cls._number(
                item.get("maximum_closed_trade_drawdown_pct"), 2
            ),
            "maximum_consecutive_losses": cls._count(
                item.get("maximum_consecutive_losses")
            ),
        }

    @classmethod
    def _sample_contract_review(cls, value: object) -> dict[str, Any]:
        item = dict(value) if isinstance(value, dict) else {}
        fingerprint = str(item.get("expected_fingerprint_sha256", ""))
        if len(fingerprint) != 64 or any(
            character not in "0123456789abcdef" for character in fingerprint
        ):
            fingerprint = ""
        return {
            "status": str(item.get("status", "CONTRACT_STATUS_MISSING"))[:80],
            "mode": "FOREX_PAPER_SAMPLE_CONTRACT_READ_ONLY",
            "contract_tracking_enabled": (
                item.get("contract_tracking_enabled") is True
            ),
            "expected_contract_id": " ".join(
                str(item.get("expected_contract_id", "")).split()
            )[:80],
            "expected_fingerprint_sha256": fingerprint,
            "current_contract_closed_trade_count": cls._count(
                item.get("current_contract_closed_trade_count")
            ),
            "legacy_unversioned_closed_trade_count": cls._count(
                item.get("legacy_unversioned_closed_trade_count")
            ),
            "foreign_contract_closed_trade_count": cls._count(
                item.get("foreign_contract_closed_trade_count")
            ),
            "superseded_contract_closed_trade_count": cls._count(
                item.get("superseded_contract_closed_trade_count")
            ),
            "all_time_closed_trade_count": cls._count(
                item.get("all_time_closed_trade_count")
            ),
            "sample_contract_consistent": (
                item.get("sample_contract_consistent") is True
            ),
            "automatic_sample_merge": False,
            "automatic_strategy_change": False,
            "live_promotion_ready": False,
        }

    @staticmethod
    def _pair_review(
        pairs: dict[str, dict[str, Any]],
        required: int,
        evidence_valid: bool,
    ) -> dict[str, Any]:
        def selected(status: str) -> list[str]:
            return [
                pair for pair, metrics in pairs.items()
                if metrics.get("review_status") == status
            ]

        ready = selected("READY_FOR_MANUAL_REVIEW")
        collecting = selected("COLLECTING_PAIR_SAMPLE")
        unobserved = selected("NO_CLOSED_TRADES")
        blocked = selected("BLOCKED_INVALID_EVIDENCE")
        return {
            "status": (
                "BLOCKED_INVALID_EVIDENCE"
                if not evidence_valid
                else (
                    "READY_FOR_MANUAL_REVIEW"
                    if len(ready) == len(pairs)
                    else "COLLECTING_PAIR_SAMPLES"
                )
            ),
            "mode": "FOREX_PAIR_REVIEW_READ_ONLY",
            "pair_count": len(pairs),
            "minimum_closed_trades_per_pair_for_review": required,
            "ready_pair_count": len(ready),
            "collecting_pair_count": len(collecting),
            "unobserved_pair_count": len(unobserved),
            "blocked_pair_count": len(blocked),
            "ready_pairs": ready,
            "collecting_pairs": collecting,
            "unobserved_pairs": unobserved,
            "blocked_pairs": blocked,
            "all_pairs_ready_for_manual_review": len(ready) == len(pairs),
            "automatic_pair_selection": False,
            "automatic_pair_disable": False,
            "live_promotion_ready": False,
        }

    @classmethod
    def _positions(cls, value: object) -> list[dict[str, str]]:
        items = list(value) if isinstance(value, list) else []
        result: list[dict[str, str]] = []
        for raw in items[:5]:
            item = dict(raw) if isinstance(raw, dict) else {}
            pair = str(item.get("pair", "")).strip().upper()
            side = str(item.get("side", "")).strip().upper()
            if pair not in _MAJOR_PAIRS or side not in {"LONG", "SHORT"}:
                continue
            result.append({
                "pair": pair,
                "side": side,
                "units": cls._number(item.get("units"), 0),
                "entry_price": cls._number(item.get("entry_price"), 6),
                "current_price": cls._number(item.get("current_price"), 6),
                "stop_loss": cls._number(item.get("stop_loss"), 6),
                "take_profit": cls._number(item.get("take_profit"), 6),
                "opened_at": " ".join(str(item.get("opened_at", "")).split())[:64],
            })
        return result

    @staticmethod
    def _number(value: object, places: int) -> str:
        try:
            number = Decimal(str(value))
            if not number.is_finite() or abs(number) > Decimal("1000000000000"):
                raise InvalidOperation
        except (InvalidOperation, TypeError, ValueError):
            number = Decimal("0")
        return f"{number:.{places}f}"

    @staticmethod
    def _count(value: object) -> int:
        try:
            return max(0, min(int(value or 0), 1_000_000))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _blocked(message: str) -> dict[str, Any]:
        return {
            "status": "BLOCKED",
            "mode": "FOREX_PAPER_ONLY",
            "positions": [],
            "position_count": 0,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "real_money_access": False,
            "message": message,
        }


__all__ = ["ForexPaperDashboard"]
