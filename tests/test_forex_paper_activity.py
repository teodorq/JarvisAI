from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.market_data.forex_environment import ForexDataSettings
from app.trading.forex_activity import ForexPaperActivityFeed


def settings(*, enabled: bool = True) -> ForexDataSettings:
    return ForexDataSettings(
        enabled=enabled,
        paper_autopilot_enabled=enabled,
        primary_provider="MT5_DEMO",
    )


class ForexPaperActivityFeedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / "data" / "trading" / "forex_paper_last.json"
        self.path.parent.mkdir(parents=True)

    def write(
        self,
        cycle: str,
        *,
        status: str = "PAPER_CYCLE_COMPLETED",
        executions: list[dict] | None = None,
        live: bool = False,
        observation: dict | None = None,
    ) -> None:
        self.path.write_text(
            json.dumps({
                "status": status,
                "cycle_id": cycle,
                "observed_at": f"2026-08-21T09:{cycle[-2:]}:00+00:00",
                "paper": {
                    "execution": {"executions": executions or []},
                },
                "broker_orders_sent": False,
                "live_orders_sent": live,
                "real_money_access": False,
                "observation": observation or {},
            }),
            encoding="utf-8",
        )

    def test_disabled_feed_never_reads_or_writes_notification_state(self) -> None:
        self.write("cycle-00")
        feed = ForexPaperActivityFeed(self.root, settings=settings(enabled=False))

        self.assertIsNone(feed.poll())
        self.assertFalse(feed.state.path.exists())

    def test_quiet_cycle_is_remembered_without_notification(self) -> None:
        self.write("cycle-01")
        feed = ForexPaperActivityFeed(self.root, settings=settings())

        self.assertIsNone(feed.poll())
        self.assertIsNone(feed.poll())
        self.assertEqual(feed.status()["notification_count"], 0)
        self.assertEqual(feed.status()["last_health"], "HEALTHY")

    def test_open_and_close_are_announced_once_without_broker_claim(self) -> None:
        feed = ForexPaperActivityFeed(self.root, settings=settings())
        self.write("cycle-02", executions=[{
            "status": "EXECUTED",
            "fill": {"action": "OPEN_LONG", "pair": "EUR_USD"},
        }])

        opened = feed.poll()
        self.assertIsNotNone(opened)
        assert opened is not None
        self.assertEqual(opened["state"], "important")
        self.assertIn("LONG na EUR/USD", opened["message"])
        self.assertIn("nie wysłałem zlecenia do brokera", opened["message"])
        self.assertIsNone(feed.poll())

        self.write("cycle-03", executions=[{
            "status": "EXECUTED",
            "fill": {
                "action": "CLOSE_LONG",
                "pair": "EUR_USD",
                "realized_pnl_pln": "12.34",
            },
        }])
        closed = feed.poll()
        self.assertIsNotNone(closed)
        assert closed is not None
        self.assertIn("zamknąłem", closed["message"])
        self.assertIn("12.34 PLN", closed["message"])
        self.assertEqual(feed.status()["notification_count"], 2)

    def test_repeated_block_is_suppressed_and_recovery_is_announced(self) -> None:
        feed = ForexPaperActivityFeed(self.root, settings=settings())
        self.write("cycle-04")
        self.assertIsNone(feed.poll())

        self.write("cycle-05", status="PAPER_CYCLE_BLOCKED")
        blocked = feed.poll()
        self.assertIsNotNone(blocked)
        assert blocked is not None
        self.assertIn("Wstrzymałem nowe wejścia", blocked["message"])

        self.write("cycle-06", status="PAPER_CYCLE_BLOCKED")
        self.assertIsNone(feed.poll())

        self.write("cycle-07")
        recovered = feed.poll()
        self.assertIsNotNone(recovered)
        assert recovered is not None
        self.assertIn("wróciły do prawidłowego stanu", recovered["message"])

    def test_macro_block_names_the_affected_pairs(self) -> None:
        feed = ForexPaperActivityFeed(self.root, settings=settings())
        self.write(
            "cycle-10",
            status="PAPER_CYCLE_BLOCKED",
            observation={
                "opening_blocks": ["HIGH_IMPACT_EVENT_WINDOW"],
                "opening_blocks_by_pair": {
                    "EUR_USD": ["HIGH_IMPACT_EVENT_WINDOW"],
                    "USD_JPY": ["HIGH_IMPACT_EVENT_WINDOW"],
                    "BAD_PAIR": ["HIGH_IMPACT_EVENT_WINDOW"],
                },
            },
        )

        blocked = feed.poll()

        self.assertIsNotNone(blocked)
        assert blocked is not None
        self.assertIn("ważnego wydarzenia makro", blocked["message"])
        self.assertIn("EUR/USD, USD/JPY", blocked["message"])
        self.assertNotIn("BAD/PAIR", blocked["message"])
        self.assertIn("zamknięcia pozostają aktywne", blocked["message"])

    def test_safety_flag_produces_owner_attention_without_live_action(self) -> None:
        self.write("cycle-08", live=True)
        feed = ForexPaperActivityFeed(self.root, settings=settings())

        event = feed.poll()
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event["state"], "important")
        self.assertIn("wymaga sprawdzenia", event["message"])
        self.assertTrue(feed.status()["live_orders_sent"] is False)

    def test_corrupted_notification_count_is_safely_reset(self) -> None:
        self.write("cycle-09")
        feed = ForexPaperActivityFeed(self.root, settings=settings())
        feed.state.save({
            "last_cycle_key": "old-cycle",
            "last_health": "HEALTHY",
            "notification_count": "not-a-number",
        })

        self.assertIsNone(feed.poll())
        self.assertEqual(feed.status()["notification_count"], 0)


if __name__ == "__main__":
    unittest.main()
