from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.market_data.forex_models import ForexDataBundle
from app.trading.forex_models import (
    ForexBar,
    ForexQuote,
    ForexSafetyContext,
    MAJOR_FOREX_PAIRS,
    USD_PLN_CONVERSION_PAIR,
)
from app.trading.forex_observation import (
    ForexObservationJournal,
    ForexObservationService,
)
from app.trading.control_center import TradingControlCenter
from app.trading.models import TradingValidationError


UTC = timezone.utc
BASE = {
    "EUR_USD": Decimal("1.1000"),
    "GBP_USD": Decimal("1.2800"),
    "USD_JPY": Decimal("150.00"),
    "USD_CHF": Decimal("0.9000"),
    "AUD_USD": Decimal("0.6600"),
    "USD_CAD": Decimal("1.3500"),
    "NZD_USD": Decimal("0.6100"),
}


def bundle(
    now: datetime,
    *,
    open_market: bool = True,
    blocked_pair: str = "",
) -> ForexDataBundle:
    quotes = {}
    bars = {}
    contexts = {}
    for pair in MAJOR_FOREX_PAIRS:
        prices = [BASE[pair.symbol]] * 31
        if pair.symbol == "EUR_USD":
            prices[-1] += pair.pip_size * Decimal("20")
        bars[pair.symbol] = tuple(
            ForexBar.create(
                pair=pair,
                timestamp=now - timedelta(seconds=(30 - index) * 900),
                open=price,
                high=price + pair.pip_size,
                low=price - pair.pip_size,
                close=price,
                tick_volume="100",
            )
            for index, price in enumerate(prices)
        )
        half = pair.pip_size / Decimal("2")
        quotes[pair.symbol] = ForexQuote.create(
            pair=pair,
            bid=prices[-1] - half,
            ask=prices[-1] + half,
            timestamp=now,
        )
        contexts[pair.symbol] = ForexSafetyContext(
            observed_at=now,
            market_open=open_market,
            calendar_ready=True,
            high_impact_event_blocked=pair.symbol == blocked_pair,
            conversion_to_pln_ready=True,
            independent_source_count=2,
        )
    conversion = ForexQuote.create(
        pair=USD_PLN_CONVERSION_PAIR,
        bid="3.999",
        ask="4.001",
        timestamp=now,
    )
    return ForexDataBundle(
        quotes=quotes,
        bars=bars,
        contexts=contexts,
        conversion_quotes=(conversion,),
        diagnostics={
            "primary_provider": "MT5_DEMO",
            "primary_pair_count": len(quotes),
            "cross_checked_pairs": tuple(quotes),
            "calendar_ready": True,
            "high_impact_event_count": 1,
            "nbp_effective_date": now.date().isoformat(),
            "pln_conversion_ready": True,
        },
    )


class FakeGateway:
    def __init__(
        self,
        *,
        failing: bool = False,
        open_market: bool = True,
    ) -> None:
        self.failing = failing
        self.open_market = open_market

    def collect(self, *, now: datetime) -> ForexDataBundle:
        if self.failing:
            raise TradingValidationError("forex_data_gate: source_unavailable")
        return bundle(now, open_market=self.open_market)


class ForexObservationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.now = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)

    def service(
        self,
        *,
        failing: bool = False,
        open_market: bool = True,
    ) -> ForexObservationService:
        return ForexObservationService(
            self.root,
            gateway=FakeGateway(
                failing=failing,
                open_market=open_market,
            ),  # type: ignore[arg-type]
        )

    def test_observation_records_plan_without_executing_it(self) -> None:
        service = self.service()
        result = service.observe_once(
            observation_id="forex-observation-0001",
            now=self.now,
        )

        self.assertEqual(result["status"], "OBSERVATION_RECORDED")
        self.assertEqual(result["proposed_plan"]["status"], "ENTRIES_READY")
        self.assertEqual(result["would_open_count"], 1)
        self.assertEqual(result["execution"]["status"], "NOT_EXECUTED")
        candidate = result["development_candidate_v2"]
        self.assertEqual(candidate["status"], "FORWARD_OBSERVATION_RECORDED")
        self.assertFalse(candidate["forward_eligible"])
        self.assertEqual(candidate["execution"]["status"], "NOT_EXECUTED")
        self.assertFalse(candidate["paper_orders_sent"])
        self.assertFalse(candidate["live_orders_sent"])
        self.assertTrue(result["positions_unchanged"])
        self.assertFalse(result["paper_orders_sent"])
        self.assertFalse(result["live_orders_sent"])
        self.assertEqual(service.executor.status()["position_count"], 0)
        self.assertFalse(
            (self.root / "data/trading/forex_paper_ledger.json").exists()
        )
        self.assertTrue(
            (self.root / "data/trading/forex_observations.json").exists()
        )

    def test_duplicate_id_is_idempotent(self) -> None:
        service = self.service()
        first = service.observe_once(
            observation_id="forex-observation-replay",
            now=self.now,
        )
        replay = service.observe_once(
            observation_id="forex-observation-replay",
            now=self.now + timedelta(seconds=1),
        )

        self.assertFalse(first["idempotent_replay"])
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(service.journal.summary()["observation_count"], 1)

    def test_observation_records_opening_blocks_by_pair(self) -> None:
        result = self.service().observe_once(
            observation_id="forex-observation-macro-block",
            now=self.now,
            bundle=bundle(self.now, blocked_pair="EUR_USD"),
        )

        self.assertEqual(result["opening_blocks"], ["HIGH_IMPACT_EVENT_WINDOW"])
        self.assertEqual(
            result["opening_blocks_by_pair"],
            {"EUR_USD": ["HIGH_IMPACT_EVENT_WINDOW"]},
        )

    def test_data_failure_is_recorded_fail_closed(self) -> None:
        service = self.service(failing=True)
        result = service.observe_once(
            observation_id="forex-observation-blocked",
            now=self.now,
        )

        self.assertEqual(result["status"], "DATA_BLOCKED")
        self.assertIn("SOURCE_UNAVAILABLE", result["opening_blocks"][0])
        self.assertEqual(result["opening_blocks_by_pair"], {})
        self.assertTrue(result["positions_unchanged"])
        self.assertEqual(result["proposed_instruction_count"], 0)
        self.assertTrue(result["market_data_network_access"])

    def test_tampering_blocks_the_journal_summary(self) -> None:
        service = self.service()
        service.observe_once(
            observation_id="forex-observation-audit",
            now=self.now,
        )
        state = service.journal.snapshot()
        state["observations"][0]["would_open_count"] = 99
        service.journal.store.save(state)

        summary = service.journal.summary()
        self.assertEqual(summary["status"], "BLOCKED")
        self.assertFalse(summary["audit_chain_valid"])
        self.assertFalse(summary["paper_promotion_ready"])

    def test_observation_threshold_is_advisory_and_research_gate_stays_closed(self) -> None:
        journal = ForexObservationJournal(self.root)
        for index in range(20):
            observed = self.now + timedelta(days=index % 3, minutes=index)
            journal.record({
                "status": "OBSERVATION_RECORDED",
                "mode": "FOREX_OBSERVATION_ONLY",
                "observation_id": f"forex-evidence-{index:04d}",
                "observed_at": observed.isoformat(),
                "market_open": True,
                "fully_cross_checked": True,
                "opening_blocks": [],
                "assessments": [
                    {"pair": pair.symbol, "action": "WATCH"}
                    for pair in MAJOR_FOREX_PAIRS
                ],
                "proposed_plan": {"instructions": []},
                "execution": {"status": "NOT_EXECUTED"},
                "positions_unchanged": True,
                "order_network_access": False,
                "paper_orders_sent": False,
                "live_orders_sent": False,
            })

        summary = journal.summary()
        self.assertTrue(summary["paper_promotion_ready"])
        self.assertFalse(summary["automatic_promotion"])
        self.assertEqual(summary["qualified_market_day_count"], 3)
        with patch.dict(
            os.environ,
            {"JARVIS_OS_FOREX_PAPER_AUTOPILOT_ENABLED": "false"},
        ):
            control_center = TradingControlCenter(self.root)
            status = control_center.status()
            rendered = control_center.format_status()
        self.assertFalse(status["forex"]["opening_gate_ready"])
        self.assertFalse(status["forex"]["historical_research"]["strategy_candidate_ready"])
        self.assertFalse(status["forex"]["automatic_paper_execution"])
        self.assertIn("kwalifikowane 20/20", rendered)
        self.assertIn("dni rynkowe 3/3", rendered)
        self.assertIn("Bramka PAPER: ZABLOKOWANA", rendered)
        self.assertIn("strategia historyczna", rendered)

    def test_review_aggregates_evidence_and_remains_read_only(self) -> None:
        service = self.service()
        service.observe_once(
            observation_id="forex-observation-review",
            now=self.now,
        )

        review = service.journal.review()

        self.assertEqual(review["status"], "COLLECTING_EVIDENCE")
        self.assertTrue(review["review_only"])
        self.assertTrue(review["audit_chain_valid"])
        self.assertEqual(review["qualified_market_open_count"], 1)
        self.assertEqual(review["qualified_market_day_count"], 1)
        self.assertEqual(review["remaining_qualified_observations"], 19)
        self.assertEqual(review["remaining_market_days"], 2)
        self.assertEqual(
            review["distributions"]["assessed_pairs"],
            {pair.symbol: 1 for pair in MAJOR_FOREX_PAIRS},
        )
        self.assertEqual(
            review["distributions"]["proposed_instruction_actions"],
            {"OPEN_LONG": 1},
        )
        self.assertTrue(review["safety"]["all_positions_unchanged"])
        self.assertTrue(review["safety"]["qualified_pair_coverage_complete"])
        self.assertFalse(review["safety"]["paper_orders_detected"])
        self.assertFalse(review["safety"]["live_orders_detected"])
        self.assertFalse(review["paper_execution_enabled"])
        self.assertFalse(review["live_execution_enabled"])

    def test_review_counts_only_safe_post_freeze_candidate_evidence(self) -> None:
        service = self.service()
        observed = datetime(2026, 8, 21, 10, 0, tzinfo=UTC)
        service.observe_once(
            observation_id="forex-candidate-forward-0001",
            now=observed,
        )

        candidate = service.journal.review()["development_candidate_v2"]

        self.assertEqual(candidate["expected_forward_observation_count"], 1)
        self.assertEqual(candidate["seen_forward_observation_count"], 1)
        self.assertEqual(candidate["valid_forward_observation_count"], 1)
        self.assertEqual(candidate["excluded_forward_observation_count"], 0)
        self.assertEqual(candidate["invalid_forward_observation_count"], 0)
        self.assertEqual(candidate["valid_forward_market_day_count"], 1)
        self.assertTrue(candidate["evidence_valid"])
        self.assertEqual(candidate["contract_issues"], {})
        comparison = candidate["signal_comparison"]
        self.assertEqual(comparison["base_entry_signal_count"], 1)
        self.assertEqual(comparison["retained_entry_signal_count"], 0)
        self.assertEqual(comparison["filtered_entry_signal_count"], 1)
        self.assertEqual(comparison["entry_signal_retention_pct"], 0.0)
        self.assertEqual(comparison["retained_entry_pairs"], {})
        self.assertEqual(
            comparison["filter_reasons"],
            {"CANDIDATE_V2_H1_HISTORY_INSUFFICIENT": 1},
        )
        self.assertFalse(candidate["strategy_performance_validated"])
        self.assertFalse(candidate["paper_execution_enabled"])
        self.assertFalse(candidate["live_execution_enabled"])
        rendered = TradingControlCenter(
            self.root
        ).format_observation_review()
        self.assertIn("Kandydat V2 forward", rendered)
        self.assertIn("odfiltrowane 1", rendered)
        self.assertIn(
            "Raport nie może zmienić stanu PAPER/LIVE ani sam awansować V2",
            rendered,
        )

    def test_review_excludes_unqualified_candidate_without_invalidating_it(
        self,
    ) -> None:
        observed = datetime(2026, 8, 21, 10, 0, tzinfo=UTC)
        self.service().observe_once(
            observation_id="forex-candidate-qualified-0001",
            now=observed,
        )
        self.service(open_market=False).observe_once(
            observation_id="forex-candidate-market-closed-0001",
            now=observed + timedelta(minutes=15),
        )

        candidate = ForexObservationJournal(self.root).review()[
            "development_candidate_v2"
        ]

        self.assertEqual(candidate["expected_forward_observation_count"], 1)
        self.assertEqual(candidate["seen_forward_observation_count"], 2)
        self.assertEqual(candidate["valid_forward_observation_count"], 1)
        self.assertEqual(candidate["excluded_forward_observation_count"], 1)
        self.assertEqual(candidate["invalid_forward_observation_count"], 0)
        self.assertEqual(
            candidate["exclusion_reasons"],
            {"BASE_OBSERVATION_NOT_QUALIFIED": 1},
        )
        self.assertEqual(candidate["contract_issues"], {})
        self.assertTrue(candidate["evidence_valid"])

    def test_review_rejects_invalid_candidate_contract(self) -> None:
        service = self.service()
        observed = datetime(2026, 8, 21, 10, 0, tzinfo=UTC)
        original = service.observe_once(
            observation_id="forex-candidate-contract-valid-0001",
            now=observed,
        )
        invalid = deepcopy(original)
        invalid["observation_id"] = "forex-candidate-contract-invalid-0001"
        invalid["observed_at"] = (
            observed + timedelta(minutes=15)
        ).isoformat()
        invalid["development_candidate_v2"][
            "policy_fingerprint_sha256"
        ] = "invalid-fingerprint"
        service.journal.record(invalid)

        review = service.journal.review()
        candidate = review["development_candidate_v2"]

        self.assertTrue(review["audit_chain_valid"])
        self.assertEqual(candidate["expected_forward_observation_count"], 2)
        self.assertEqual(candidate["seen_forward_observation_count"], 2)
        self.assertEqual(candidate["valid_forward_observation_count"], 1)
        self.assertEqual(candidate["invalid_forward_observation_count"], 1)
        self.assertEqual(
            candidate["contract_issues"],
            {"POLICY_FINGERPRINT_MISMATCH": 1},
        )
        self.assertFalse(candidate["evidence_valid"])

    def test_review_blocks_incomplete_safety_evidence(self) -> None:
        journal = ForexObservationJournal(self.root)
        journal.record({
            "status": "OBSERVATION_RECORDED",
            "mode": "FOREX_OBSERVATION_ONLY",
            "observation_id": "forex-incomplete-review",
            "observed_at": self.now.isoformat(),
            "market_open": True,
            "fully_cross_checked": True,
            "paper_orders_sent": False,
            "live_orders_sent": False,
        })

        review = journal.review()

        self.assertEqual(review["status"], "BLOCKED")
        self.assertIn("ORDER_NETWORK_ACCESS_DETECTED", review["issues"])
        self.assertIn("POSITION_STATE_CHANGED", review["issues"])
        self.assertIn("EXECUTION_STATUS_INVALID", review["issues"])
        self.assertIn("QUALIFIED_PAIR_COVERAGE_INCOMPLETE", review["issues"])
        self.assertFalse(review["owner_review_ready"])
        self.assertEqual(journal.summary()["status"], "BLOCKED")
        self.assertFalse(journal.summary()["paper_promotion_ready"])


if __name__ == "__main__":
    unittest.main()
