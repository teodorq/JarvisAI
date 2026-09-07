"""Durable, bounded history for local Forex PAPER notifications."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Iterator

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.trading.forex_entry_blocks import activity_block_message


_PAIR = re.compile(r"^[A-Z]{3}_[A-Z]{3}$")


class ForexPaperActivityJournal:
    """Record safe display events even while the JARVIS window is closed."""

    MAX_EVENTS = 512
    MAX_RECENT_CYCLES = 1024
    MAX_LEDGER_BYTES = 12_000_000

    def __init__(self, project_root: str | Path | None = None) -> None:
        root = resolve_project_root(project_root)
        directory = root / "data" / "trading"
        self.path = directory / "forex_paper_activity_history.json"
        self.lock_path = directory / ".forex_paper_activity_history.lock"
        self.ledger_path = directory / "forex_paper_ledger.json"
        self.store = JsonStore(self.path, self._default)

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "schema_version": 1,
            "mode": "FOREX_PAPER_ONLY",
            "next_sequence": 1,
            "last_cycle_key": "",
            "last_health": "",
            "last_protection_health": "",
            "protection_consecutive_failure_count": 0,
            "recent_cycle_keys": [],
            "events": [],
            "dropped_event_count": 0,
        }

    def initialize(self) -> dict[str, Any]:
        """Create the journal and backfill old fills before a new cycle runs."""
        if self.store.exists():
            return self.status()
        with self._exclusive_lock():
            if not self.store.exists():
                state = self._default()
                fills = self._ledger_fills()
                for index, fill in enumerate(fills[-self.MAX_EVENTS:]):
                    spec = self._execution_spec(fill)
                    if spec is not None:
                        self._append(
                            state,
                            spec,
                            cycle_key=f"ledger:{self._fill_token(fill, index)}",
                            origin="LEDGER_BACKFILL",
                        )
                state["dropped_event_count"] = max(
                    0, len(fills) - len(state["events"])
                )
                self.store.save(state)
        return self.status()

    def record(self, payload: object) -> dict[str, Any]:
        """Persist all new events represented by one completed watchdog result."""
        value = dict(payload) if isinstance(payload, dict) else {}
        cycle_key = self._cycle_key(value)
        if not cycle_key:
            return {"status": "INVALID_CYCLE", "events_recorded": 0}
        self.initialize()
        with self._exclusive_lock():
            state = self._normalized(self.store.load())
            if cycle_key in state["recent_cycle_keys"]:
                return {"status": "DUPLICATE_CYCLE", "events_recorded": 0}
            health = self._health(value)
            specs = self._event_specs(value, previous_health=state["last_health"])
            recorded = 0
            for spec in specs:
                recorded += self._append(
                    state,
                    spec,
                    cycle_key=cycle_key,
                    origin="WATCHDOG_CYCLE",
                )
            state["last_cycle_key"] = cycle_key
            state["last_health"] = health
            state["recent_cycle_keys"] = (
                state["recent_cycle_keys"] + [cycle_key]
            )[-self.MAX_RECENT_CYCLES:]
            self._trim(state)
            self.store.save(state)
        return {"status": "RECORDED", "events_recorded": recorded}

    def events(
        self,
        *,
        after_sequence: int = 0,
        limit: int = 50,
        newest: bool = False,
    ) -> list[dict[str, Any]]:
        self.initialize()
        state = self._normalized(self.store.load())
        selected_limit = max(1, min(int(limit), self.MAX_EVENTS))
        selected = [
            dict(item)
            for item in state["events"]
            if int(item["sequence"]) > max(0, int(after_sequence))
        ]
        return selected[-selected_limit:] if newest else selected[:selected_limit]

    def record_protection_health(self, payload: object) -> dict[str, Any]:
        """Persist sustained protection trouble and its recovery without spam."""
        value = dict(payload) if isinstance(payload, dict) else {}
        cycle_key = self._cycle_key(value)
        if not cycle_key or any(
            value.get(key) is not False
            for key in (
                "broker_orders_sent",
                "live_orders_sent",
                "real_money_access",
            )
        ):
            return {"status": "INVALID_PROTECTION_HEALTH", "events_recorded": 0}
        result_status = str(value.get("status", ""))[:80]
        healthy = result_status in {
            "NO_OPEN_POSITIONS",
            "NO_PROTECTION_TRIGGER",
            "PAPER_PROTECTION_APPLIED",
        }
        reason = " ".join(str(value.get("reason", "")).split())[:160]
        occurred_at = " ".join(str(value.get("observed_at", "")).split())[:64]
        self.initialize()
        with self._exclusive_lock():
            state = self._normalized(self.store.load())
            previous = state["last_protection_health"]
            failures = 0 if healthy else min(
                1_000,
                int(state["protection_consecutive_failure_count"]) + 1,
            )
            current = "HEALTHY" if healthy else (
                "ATTENTION" if failures >= 3 else "DEGRADED"
            )
            spec = None
            if current == "ATTENTION" and previous != "ATTENTION":
                detail = reason or result_status or "wynik ochrony jest niedostępny"
                spec = self._spec(
                    "POSITION_PROTECTION_ATTENTION",
                    "important",
                    "Ochrona SL/TP pozycji PAPER nie przeszła trzech kolejnych "
                    f"kontroli ({detail}). Pełny cykl pozostaje aktywny, a "
                    "zlecenia LIVE są niedostępne.",
                    occurred_at,
                    f"protection-attention:{cycle_key}",
                )
            elif current == "HEALTHY" and previous == "ATTENTION":
                spec = self._spec(
                    "POSITION_PROTECTION_RECOVERED",
                    "brief",
                    "Ochrona SL/TP pozycji PAPER ponownie działa prawidłowo; "
                    "licznik kolejnych problemów został wyzerowany.",
                    occurred_at,
                    f"protection-recovered:{cycle_key}",
                )
            recorded = 0
            if spec is not None:
                recorded = self._append(
                    state,
                    spec,
                    cycle_key=cycle_key,
                    origin="PROTECTION_WATCHDOG",
                )
            state["last_protection_health"] = current
            state["protection_consecutive_failure_count"] = failures
            self._trim(state)
            self.store.save(state)
        return {
            "status": "RECORDED",
            "events_recorded": recorded,
            "protection_health": current,
            "consecutive_failure_count": failures,
            "attention_required": current == "ATTENTION",
        }

    def status(self) -> dict[str, Any]:
        state = self._normalized(self.store.load())
        return {
            "status": "FOREX_PAPER_ACTIVITY_HISTORY_READY",
            "event_count": len(state["events"]),
            "latest_sequence": max(
                (int(item["sequence"]) for item in state["events"]),
                default=0,
            ),
            "dropped_event_count": state["dropped_event_count"],
            "last_health": state["last_health"],
            "last_protection_health": state["last_protection_health"],
            "protection_consecutive_failure_count": state[
                "protection_consecutive_failure_count"
            ],
            "broker_orders_sent": False,
            "live_orders_sent": False,
        }

    def _append(
        self,
        state: dict[str, Any],
        spec: dict[str, str],
        *,
        cycle_key: str,
        origin: str,
    ) -> int:
        token = str(spec.get("token", "")) or f"{cycle_key}:{spec['kind']}"
        event_id = hashlib.sha256(token.encode("utf-8")).hexdigest()[:24]
        if any(item.get("event_id") == event_id for item in state["events"]):
            return 0
        sequence = int(state["next_sequence"])
        state["next_sequence"] = sequence + 1
        state["events"].append({
            "sequence": sequence,
            "event_id": event_id,
            "cycle_key": cycle_key[:192],
            "occurred_at": str(spec.get("occurred_at", ""))[:64],
            "kind": str(spec.get("kind", "ACTIVITY"))[:48],
            "origin": origin,
            "state": "important"
            if spec.get("state") == "important"
            else "brief",
            "message": " ".join(str(spec.get("message", "")).split())[:420],
            "progress": 0,
            "requires_confirmation": False,
            "result_type": "FOREX_PAPER_ACTIVITY",
        })
        return 1

    def _event_specs(
        self,
        payload: dict[str, Any],
        *,
        previous_health: str,
    ) -> list[dict[str, str]]:
        health = self._health(payload)
        occurred_at = " ".join(str(payload.get("observed_at", "")).split())[:64]
        if health == "SAFETY_ATTENTION":
            return [self._spec(
                "SAFETY_ATTENTION",
                "important",
                "Wykryłem niespójny raport Forex PAPER. Wynik wymaga sprawdzenia "
                "w trybie właściciela; zlecenia LIVE pozostają niedostępne.",
                occurred_at,
            )]
        specs = [
            spec
            for execution in self._executions(payload)
            if (spec := self._execution_spec(
                dict(execution.get("fill", {}) or {})
            )) is not None
        ]
        for spec in specs:
            spec["occurred_at"] = occurred_at or spec.get("occurred_at", "")
        if specs:
            return specs
        if health == "BLOCKED" and previous_health != "BLOCKED":
            return [self._spec(
                "DATA_BLOCKED",
                "brief",
                activity_block_message(payload),
                occurred_at,
            )]
        if health == "HEALTHY" and previous_health == "BLOCKED":
            return [self._spec(
                "DATA_RECOVERED",
                "brief",
                "Dane Forex PAPER wróciły do prawidłowego stanu. Ponownie analizuję "
                "7 par wyłącznie w lokalnej symulacji.",
                occurred_at,
            )]
        return []

    @classmethod
    def _execution_spec(cls, fill: dict[str, Any]) -> dict[str, str] | None:
        action = str(fill.get("action", "")).strip().upper()
        pair = str(fill.get("pair", "")).strip().upper()
        if action not in {
            "OPEN_LONG", "OPEN_SHORT", "CLOSE_LONG", "CLOSE_SHORT"
        } or not _PAIR.fullmatch(pair):
            return None
        visible_pair = pair.replace("_", "/")
        token = "fill:" + cls._fill_token(fill, 0)
        occurred_at = " ".join(
            str(fill.get("filled_at") or fill.get("opened_at") or "").split()
        )[:64]
        if action.startswith("OPEN_"):
            side = action.removeprefix("OPEN_")
            message = (
                f"Forex PAPER: otworzyłem symulowaną pozycję {side} na "
                f"{visible_pair}. To wyłącznie lokalna symulacja — nie wysłałem "
                "zlecenia do brokera."
            )
            return cls._spec(
                "POSITION_OPENED", "important", message, occurred_at, token
            )
        side = action.removeprefix("CLOSE_")
        pnl = cls._pnl(fill.get("realized_pnl_pln"))
        message = (
            f"Forex PAPER: zamknąłem symulowaną pozycję {side} na {visible_pair}; "
            f"wynik {pnl} PLN. To wyłącznie lokalna symulacja — nie wysłałem "
            "zlecenia do brokera."
        )
        return cls._spec(
            "POSITION_CLOSED", "important", message, occurred_at, token
        )

    @staticmethod
    def _spec(
        kind: str,
        state: str,
        message: str,
        occurred_at: str,
        token: str = "",
    ) -> dict[str, str]:
        return {
            "kind": kind,
            "state": state,
            "message": message,
            "occurred_at": occurred_at,
            "token": token,
        }

    @staticmethod
    def _executions(payload: dict[str, Any]) -> list[dict[str, Any]]:
        paper = payload.get("paper")
        paper = dict(paper) if isinstance(paper, dict) else {}
        execution = paper.get("execution")
        execution = dict(execution) if isinstance(execution, dict) else {}
        return [
            dict(item)
            for item in list(execution.get("executions", []) or [])[:20]
            if isinstance(item, dict) and item.get("status") == "EXECUTED"
        ]

    @staticmethod
    def _cycle_key(payload: dict[str, Any]) -> str:
        cycle_id = " ".join(str(payload.get("cycle_id", "")).split())[:96]
        observed_at = " ".join(str(payload.get("observed_at", "")).split())[:64]
        return f"{cycle_id}|{observed_at}" if cycle_id or observed_at else ""

    @staticmethod
    def _health(payload: dict[str, Any]) -> str:
        if any(
            payload.get(key) is not False
            for key in ("broker_orders_sent", "live_orders_sent", "real_money_access")
        ):
            return "SAFETY_ATTENTION"
        return (
            "HEALTHY"
            if payload.get("status") in {
                "PAPER_CYCLE_COMPLETED",
                "PAPER_PROTECTION_APPLIED",
            }
            else "BLOCKED"
        )

    @staticmethod
    def _fill_token(fill: dict[str, Any], index: int) -> str:
        fill_id = " ".join(str(fill.get("fill_id", "")).split())[:128]
        if fill_id:
            return fill_id
        values = (
            fill.get("action"), fill.get("pair"), fill.get("filled_at"),
            fill.get("opened_at"), fill.get("entry_price"), index,
        )
        return "|".join(
            " ".join(str(value if value is not None else "").split())[:64]
            for value in values
        )

    @staticmethod
    def _pnl(value: object) -> str:
        try:
            number = Decimal(str(value))
            if not number.is_finite() or abs(number) > Decimal("1000000000000"):
                raise InvalidOperation
        except (InvalidOperation, TypeError, ValueError):
            number = Decimal("0")
        return f"{number:.2f}"

    def _ledger_fills(self) -> list[dict[str, Any]]:
        try:
            size = self.ledger_path.stat().st_size
            if size <= 0 or size > self.MAX_LEDGER_BYTES:
                return []
            value = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return []
        ledger = dict(value) if isinstance(value, dict) else {}
        if ledger.get("mode") != "FOREX_PAPER_ONLY":
            return []
        return [
            dict(item)
            for item in list(ledger.get("fills", []) or [])
            if isinstance(item, dict)
        ]

    def _normalized(self, value: object) -> dict[str, Any]:
        state = self._default()
        if isinstance(value, dict):
            for key in state:
                if key in value:
                    state[key] = value[key]
        state["schema_version"] = 1
        state["mode"] = "FOREX_PAPER_ONLY"
        state["last_cycle_key"] = str(state.get("last_cycle_key", ""))[:192]
        health = str(state.get("last_health", ""))
        state["last_health"] = (
            health if health in {"HEALTHY", "BLOCKED", "SAFETY_ATTENTION"} else ""
        )
        protection_health = str(state.get("last_protection_health", ""))
        state["last_protection_health"] = (
            protection_health
            if protection_health in {"HEALTHY", "DEGRADED", "ATTENTION"}
            else ""
        )
        try:
            protection_failures = int(
                state.get("protection_consecutive_failure_count", 0) or 0
            )
        except (TypeError, ValueError):
            protection_failures = 0
        state["protection_consecutive_failure_count"] = max(
            0, min(protection_failures, 1_000)
        )
        recent = state.get("recent_cycle_keys")
        recent = recent if isinstance(recent, list) else []
        state["recent_cycle_keys"] = [
            str(item)[:192]
            for item in recent
        ][-self.MAX_RECENT_CYCLES:]
        raw_events = state.get("events")
        raw_events = raw_events if isinstance(raw_events, list) else []
        events = []
        for raw in raw_events:
            if not isinstance(raw, dict):
                continue
            try:
                sequence = int(raw.get("sequence", 0) or 0)
            except (TypeError, ValueError):
                continue
            if sequence <= 0:
                continue
            item = dict(raw)
            item["sequence"] = sequence
            item["message"] = " ".join(
                str(item.get("message", "")).split()
            )[:420]
            events.append(item)
        state["events"] = sorted(events, key=lambda item: int(item["sequence"]))
        highest = max((int(item["sequence"]) for item in events), default=0)
        try:
            next_sequence = int(state.get("next_sequence", 1) or 1)
        except (TypeError, ValueError):
            next_sequence = 1
        state["next_sequence"] = max(highest + 1, next_sequence)
        try:
            dropped = int(state.get("dropped_event_count", 0) or 0)
        except (TypeError, ValueError):
            dropped = 0
        state["dropped_event_count"] = max(0, min(dropped, 1_000_000))
        return state

    def _trim(self, state: dict[str, Any]) -> None:
        if len(state["events"]) <= self.MAX_EVENTS:
            return
        removed = len(state["events"]) - self.MAX_EVENTS
        state["events"] = state["events"][-self.MAX_EVENTS:]
        state["dropped_event_count"] = min(
            1_000_000, int(state["dropped_event_count"]) + removed
        )

    @contextmanager
    def _exclusive_lock(self) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + 5.0
        descriptor: int | None = None
        while descriptor is None:
            try:
                descriptor = os.open(
                    self.lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
            except FileExistsError:
                try:
                    stale = time.time() - self.lock_path.stat().st_mtime > 60
                    if stale:
                        self.lock_path.unlink()
                        continue
                except OSError:
                    pass
                if time.monotonic() >= deadline:
                    raise TimeoutError("Forex PAPER activity history lock timeout")
                time.sleep(0.05)
        try:
            os.write(descriptor, str(os.getpid()).encode("ascii"))
            yield
        finally:
            os.close(descriptor)
            try:
                self.lock_path.unlink()
            except FileNotFoundError:
                pass


__all__ = ["ForexPaperActivityJournal"]
