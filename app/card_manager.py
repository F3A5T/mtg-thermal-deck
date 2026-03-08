import json
import logging
import os
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

    def reload(self):
        self._index.clear()
        self._load_index()
