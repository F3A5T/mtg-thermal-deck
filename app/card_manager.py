import json
import logging
import os
import random
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class Card:
    def __init__(self, data: dict):
        self.id: str = data.get("id", "")
        self.name: str = data.get("name", "Unknown")
        self.mana_cost: str = data.get("mana_cost", "")
        self.cmc: int = int(data.get("cmc", 0))
        self.type_line: str = data.get("type_line", "")
        self.colors: List[str] = data.get("colors", [])
        self.power: Optional[str] = data.get("power")
        self.toughness: Optional[str] = data.get("toughness")
        self.oracle_text: str = data.get("oracle_text", "")
        self.image_path: Optional[str] = data.get("image_path")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "mana_cost": self.mana_cost,
            "cmc": self.cmc,
            "type_line": self.type_line,
            "colors": self.colors,
            "power": self.power,
            "toughness": self.toughness,
            "oracle_text": self.oracle_text,
            "image_path": self.image_path,
        }


class CardManager:
    def __init__(self, cards_dir: str):
        self.cards_dir = Path(cards_dir)
        self._index: dict[int, List[Card]] = {}
        self._load_index()

    def _load_index(self):
        index_path = self.cards_dir / "index.json"
        if not index_path.exists():
            logger.warning(
                "Card index not found at %s — run scripts/fetch_cards.py first.", index_path
            )
            return

        with open(index_path, encoding="utf-8") as f:
            raw: dict = json.load(f)

        self._index = {int(k): [Card(c) for c in v] for k, v in raw.items()}
        total = sum(len(v) for v in self._index.values())
        logger.info("Loaded %d cards across %d CMC values", total, len(self._index))

    def get_cards_at_cmc(self, cmc: int) -> List[Card]:
        return self._index.get(cmc, [])

    def get_card_count_at_cmc(self, cmc: int) -> int:
        return len(self.get_cards_at_cmc(cmc))

    def get_available_cmcs(self) -> List[int]:
        return sorted(self._index.keys())

    def all_cards(self) -> List[Card]:
        """Return every card as a flat list."""
        return [c for cards in self._index.values() for c in cards]

    def filter_cards(
        self,
        cmc: Optional[int] = None,
        color: Optional[str] = None,
        type_keyword: Optional[str] = None,
    ) -> List[Card]:
        """Return cards matching all supplied filters (None = any)."""
        cards = self.all_cards()
        if cmc is not None:
            cards = [c for c in cards if c.cmc == cmc]
        if color:
            if color == "C":
                cards = [c for c in cards if not c.colors]
            else:
                cards = [c for c in cards if color in c.colors]
        if type_keyword:
            kw = type_keyword.lower()
            cards = [c for c in cards if kw in c.type_line.lower()]
        return cards

    def get_card_by_id(self, card_id: str) -> Optional[Card]:
        for cards in self._index.values():
            for c in cards:
                if c.id == card_id:
                    return c
        return None

    def random_card(
        self,
        cmc: Optional[int] = None,
        color: Optional[str] = None,
        type_keyword: Optional[str] = None,
    ) -> Optional[Card]:
        pool = self.filter_cards(cmc=cmc, color=color, type_keyword=type_keyword)
        return random.choice(pool) if pool else None

    def reload(self):
        self._index.clear()
        self._load_index()
