"""Sanitized explanations for Forex PAPER entry blocks."""

from __future__ import annotations

from typing import Any


MAJOR_PAIRS = (
    "EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF",
    "AUD_USD", "USD_CAD", "NZD_USD",
)
OPENING_BLOCK_CODES = {
    "MARKET_CLOSED",
    "ECONOMIC_CALENDAR_UNAVAILABLE",
    "HIGH_IMPACT_EVENT_WINDOW",
    "PLN_CONVERSION_UNAVAILABLE",
    "SECOND_SOURCE_UNAVAILABLE",
}


def opening_block_details(
    payload: dict[str, Any],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return only allowlisted block codes and major pairs in fixed order."""
    observation = payload.get("observation")
    observation = dict(observation) if isinstance(observation, dict) else {}
    raw_codes = observation.get("opening_blocks")
    raw_codes = raw_codes if isinstance(raw_codes, (list, tuple)) else ()
    codes = {
        str(code) for code in raw_codes if str(code) in OPENING_BLOCK_CODES
    }
    raw_by_pair = observation.get("opening_blocks_by_pair")
    by_pair = dict(raw_by_pair) if isinstance(raw_by_pair, dict) else {}
    pairs: list[str] = []
    for pair in MAJOR_PAIRS:
        raw_pair_codes = by_pair.get(pair)
        if not isinstance(raw_pair_codes, (list, tuple)):
            continue
        pair_codes = {
            str(code)
            for code in raw_pair_codes
            if str(code) in OPENING_BLOCK_CODES
        }
        if pair_codes:
            pairs.append(pair)
            codes.update(pair_codes)
    return tuple(sorted(codes)), tuple(pairs)


def activity_block_message(payload: dict[str, Any]) -> str:
    codes, pairs = opening_block_details(payload)
    visible_pairs = ", ".join(pair.replace("_", "/") for pair in pairs)
    if "HIGH_IMPACT_EVENT_WINDOW" in codes:
        scope = f" dla: {visible_pairs}" if visible_pairs else ""
        return (
            "Wstrzymałem nowe wejścia Forex PAPER z powodu okna ważnego "
            f"wydarzenia makro{scope}. Zweryfikowane zamknięcia pozostają "
            "aktywne; sprawdzę rynek ponownie automatycznie. LIVE jest "
            "niedostępny."
        )
    if "MARKET_CLOSED" in codes:
        return (
            "Wstrzymałem nowe wejścia Forex PAPER, ponieważ rynek jest teraz "
            "zamknięty. Sprawdzę go ponownie automatycznie; LIVE jest "
            "niedostępny."
        )
    return (
        "Wstrzymałem nowe wejścia Forex PAPER, ponieważ bieżąca kontrola "
        "danych nie przeszła. Zweryfikowane zamknięcia pozostają aktywne; "
        "sprawdzę rynek ponownie automatycznie. LIVE jest niedostępny."
    )


def dashboard_block_message(
    codes: tuple[str, ...],
    pairs: tuple[str, ...],
) -> str:
    visible_pairs = ", ".join(pair.replace("_", "/") for pair in pairs)
    if "HIGH_IMPACT_EVENT_WINDOW" in codes:
        scope = f" dla: {visible_pairs}" if visible_pairs else ""
        return (
            "Nowe wejścia PAPER są wstrzymane przez ważne wydarzenie makro"
            f"{scope}; zweryfikowane zamknięcia nadal działają."
        )
    if "MARKET_CLOSED" in codes:
        return (
            "Rynek Forex jest teraz zamknięty; JARVIS sprawdzi go ponownie "
            "automatycznie."
        )
    return (
        "Nowe wejścia PAPER są wstrzymane przez bieżącą kontrolę danych; "
        "zweryfikowane zamknięcia nadal działają."
    )


__all__ = [
    "activity_block_message",
    "dashboard_block_message",
    "opening_block_details",
]
