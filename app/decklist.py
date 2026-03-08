"""
Decklist fetching from Moxfield and Archidekt.

Usage:
    from app.decklist import load_deck_from_url, DeckCard
    name, cards = load_deck_from_url("https://www.moxfield.com/decks/abc123")
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "MTGConsole/1.0"}
_TIMEOUT = 20

# Categories we include when printing "all"
PRINT_CATEGORIES = {"mainboard", "commander", "main"}


@dataclass
class DeckCard:
    name: str
    quantity: int
    category: str       # mainboard / sideboard / commander / etc.
    card: object = None # resolved Card or Token (duck-typed)
    found: bool = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "quantity": self.quantity,
            "category": self.category,
            "found": self.found,
            "card": self.card.to_dict() if self.card else None,
        }


# ---------------------------------------------------------------------------
# Moxfield
# ---------------------------------------------------------------------------

def _fetch_moxfield(deck_id: str) -> tuple[str, list[DeckCard]]:
    url = f"https://api2.moxfield.com/v3/decks/all/{deck_id}"
    logger.info("Fetching Moxfield deck: %s", deck_id)
    r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    r.raise_for_status()
    data = r.json()

    deck_name = data.get("name", "Untitled")
    cards: list[DeckCard] = []

    for board_name, board in data.get("boards", {}).items():
        # Skip non-card boards
        if board_name in ("tokens", "attractions", "contraptions"):
            continue
        for entry in board.get("cards", {}).values():
            cards.append(DeckCard(
                name=entry["card"]["name"],
                quantity=entry.get("quantity", 1),
                category=board_name.lower(),
            ))

    return deck_name, cards


# ---------------------------------------------------------------------------
# Archidekt
# ---------------------------------------------------------------------------

def _fetch_archidekt(deck_id: str) -> tuple[str, list[DeckCard]]:
    url = f"https://archidekt.com/api/decks/{deck_id}/small/"
    logger.info("Fetching Archidekt deck: %s", deck_id)
    r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    r.raise_for_status()
    data = r.json()

    deck_name = data.get("name", "Untitled")
    cards: list[DeckCard] = []

    for entry in data.get("cards", []):
        category = (entry.get("category") or "Mainboard").lower()
        if category == "token":
            continue
        card_data = entry.get("card", {})
        oracle = card_data.get("oracleCard", card_data)
        name = oracle.get("name", "")
        if not name:
            continue
        cards.append(DeckCard(
            name=name,
            quantity=entry.get("quantity", 1),
            category=category,
        ))

    return deck_name, cards


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def load_deck_from_url(url: str) -> tuple[str, list[DeckCard]]:
    """Detect source from URL and fetch deck.  Returns (deck_name, [DeckCard])."""
    url = url.strip()

    m = re.search(r"moxfield\.com/decks/([A-Za-z0-9_-]+)", url)
    if m:
        return _fetch_moxfield(m.group(1))

    a = re.search(r"archidekt\.com/decks/(\d+)", url)
    if a:
        return _fetch_archidekt(a.group(1))

    raise ValueError(f"Unsupported deck URL. Paste a Moxfield or Archidekt link.")
