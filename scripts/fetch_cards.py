#!/usr/bin/env python3
"""
Download card data and artwork from Scryfall for Momir Basic.

- Pulls Scryfall's oracle_cards bulk data
- Filters for all unique creature cards
- Downloads art_crop images organised by CMC
- Writes data/cards/index.json for the main app to load

Usage:
    python scripts/fetch_cards.py
    python scripts/fetch_cards.py --max-per-cmc 5   # quick test run
    python scripts/fetch_cards.py --dry-run          # no downloads
    python scripts/fetch_cards.py --cmc 3 4 5        # specific CMCs only
"""

import argparse
import json
import logging
import os
import random
import sys
import tempfile
import time
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SCRYFALL_BULK_API = "https://api.scryfall.com/bulk-data"
REQUEST_DELAY = 0.1  # Scryfall asks for >= 50–100 ms between requests

DEFAULT_DATA_DIR = Path(__file__).parent.parent / "data" / "cards"


# ---------------------------------------------------------------------------
# Fetch bulk data
# ---------------------------------------------------------------------------

def _get_bulk_url() -> str:
    logger.info("Fetching Scryfall bulk-data index...")
    r = requests.get(SCRYFALL_BULK_API, timeout=30)
    r.raise_for_status()
    for item in r.json()["data"]:
        if item["type"] == "oracle_cards":
            return item["download_uri"]
    raise RuntimeError("oracle_cards bulk data not found in Scryfall API response")


def _download_bulk(url: str) -> list:
    logger.info("Downloading bulk card data (this may take a minute)...")
    with requests.get(url, stream=True, timeout=180) as r:
        r.raise_for_status()
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".json", delete=False) as f:
            tmp = f.name
            downloaded = 0
            for chunk in r.iter_content(chunk_size=2 * 1024 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
                logger.info("  %d MB...", downloaded // 1024 // 1024)

    logger.info("Parsing JSON...")
    with open(tmp, encoding="utf-8") as f:
        data = json.load(f)
    os.unlink(tmp)
    logger.info("Loaded %d cards from bulk data", len(data))
    return data


# ---------------------------------------------------------------------------
# Filter
# ---------------------------------------------------------------------------

def _extract_creatures(cards: list, only_cmcs: list[int] | None = None) -> dict[int, list]:
    """Return {cmc: [card_entry, ...]} for all creature cards."""
    by_cmc: dict[int, list] = {}

    for card in cards:
        type_line = card.get("type_line", "")
        if "Creature" not in type_line:
            continue
        if card.get("digital", False):
            continue

        # Resolve image: normal card or first face of a DFC
        image_uris = card.get("image_uris") or {}
        if not image_uris.get("art_crop"):
            faces = card.get("card_faces") or []
            if faces:
                image_uris = faces[0].get("image_uris") or {}
            if not image_uris.get("art_crop"):
                continue

        cmc = int(card.get("cmc", 0))
        if only_cmcs and cmc not in only_cmcs:
            continue

        # Mana cost: prefer top-level, fall back to first face
        mana_cost = card.get("mana_cost") or ""
        if not mana_cost:
            faces = card.get("card_faces") or []
            mana_cost = faces[0].get("mana_cost", "") if faces else ""

        entry = {
            "id": card.get("id", ""),
            "name": card.get("name", ""),
            "mana_cost": mana_cost,
            "cmc": cmc,
            "type_line": type_line,
            "power": card.get("power"),
            "toughness": card.get("toughness"),
            "image_url": image_uris["art_crop"],
            "image_path": None,
        }
        by_cmc.setdefault(cmc, []).append(entry)

    total = sum(len(v) for v in by_cmc.values())
    logger.info(
        "Found %d unique creatures across CMC %s",
        total,
        sorted(by_cmc.keys()),
    )
    return by_cmc


# ---------------------------------------------------------------------------
# Download images
# ---------------------------------------------------------------------------

def _download_images(
    by_cmc: dict[int, list],
    data_dir: Path,
    max_per_cmc: int | None,
    dry_run: bool,
) -> dict[int, list]:
    data_dir.mkdir(parents=True, exist_ok=True)
    dl = skipped = failed = 0

    for cmc, cards in sorted(by_cmc.items()):
        cmc_dir = data_dir / str(cmc)
        cmc_dir.mkdir(exist_ok=True)

        pool = cards
        if max_per_cmc:
            pool = random.sample(cards, min(max_per_cmc, len(cards)))

        logger.info("CMC %d — %d cards", cmc, len(pool))

        for card in pool:
            dest = cmc_dir / f"{card['id']}.jpg"
            card["image_path"] = str(dest)

            if dest.exists():
                skipped += 1
                continue

            if dry_run:
                logger.debug("  [DRY RUN] %s", card["name"])
                continue

            try:
                r = requests.get(card["image_url"], timeout=30)
                r.raise_for_status()
                dest.write_bytes(r.content)
                dl += 1
            except Exception as exc:
                logger.warning("  FAILED %s: %s", card["name"], exc)
                card["image_path"] = None
                failed += 1

            time.sleep(REQUEST_DELAY)

        # Replace the full list with our (possibly sampled) pool
        by_cmc[cmc] = pool

    logger.info("Images: %d downloaded, %d already existed, %d failed", dl, skipped, failed)
    return by_cmc


# ---------------------------------------------------------------------------
# Save index
# ---------------------------------------------------------------------------

def _save_index(by_cmc: dict[int, list], data_dir: Path):
    index: dict[str, list] = {}
    for cmc, cards in by_cmc.items():
        valid = [
            {k: v for k, v in c.items() if k != "image_url"}
            for c in cards
            if c.get("image_path") and Path(c["image_path"]).exists()
        ]
        if valid:
            index[str(cmc)] = valid

    index_path = data_dir / "index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    total = sum(len(v) for v in index.values())
    logger.info("Saved index: %d cards -> %s", total, index_path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description="Fetch MTG card data for the console printer")
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    p.add_argument("--max-per-cmc", type=int, default=None,
                   help="Download at most N images per CMC (useful for testing)")
    p.add_argument("--cmc", type=int, nargs="+", default=None,
                   help="Only download cards at these CMC values")
    p.add_argument("--dry-run", action="store_true",
                   help="Parse and filter but skip image downloads")
    args = p.parse_args()

    try:
        url = _get_bulk_url()
        all_cards = _download_bulk(url)
        by_cmc = _extract_creatures(all_cards, only_cmcs=args.cmc)
        by_cmc = _download_images(by_cmc, args.data_dir, args.max_per_cmc, args.dry_run)
        if not args.dry_run:
            _save_index(by_cmc, args.data_dir)
        logger.info("Done.")
    except KeyboardInterrupt:
        logger.info("Interrupted — partial index may exist.")
        sys.exit(1)
    except Exception as exc:
        logger.error("Fatal: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
