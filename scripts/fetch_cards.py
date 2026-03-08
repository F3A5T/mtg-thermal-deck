#!/usr/bin/env python3
"""
Download card data and artwork from Scryfall for Momir Basic.

- Pulls Scryfall's oracle_cards bulk data
- Streams and filters for creature cards (low memory usage)
- Downloads art_crop images organised by CMC
- Writes data/cards/index.json for the main app to load

Usage:
    python scripts/fetch_cards.py
    python scripts/fetch_cards.py --max-per-cmc 5   # quick test run
    python scripts/fetch_cards.py --dry-run          # no image downloads
    python scripts/fetch_cards.py --cmc 3 4 5        # specific CMCs only
"""

import argparse
import json
import logging
import os
import random
import sys
import time
from pathlib import Path

import requests
import ijson

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SCRYFALL_BULK_API = "https://api.scryfall.com/bulk-data"
REQUEST_DELAY = 0.1  # Scryfall asks for >= 50–100 ms between requests

DEFAULT_DATA_DIR = Path(__file__).parent.parent / "data" / "cards"


# ---------------------------------------------------------------------------
# Fetch bulk data URL
# ---------------------------------------------------------------------------

def _get_bulk_url() -> str:
    logger.info("Fetching Scryfall bulk-data index...")
    r = requests.get(SCRYFALL_BULK_API, timeout=30)
    r.raise_for_status()
    for item in r.json()["data"]:
        if item["type"] == "oracle_cards":
            return item["download_uri"]
    raise RuntimeError("oracle_cards bulk data not found in Scryfall API response")


# ---------------------------------------------------------------------------
# Stream-parse and filter in one pass (avoids loading full JSON into RAM)
# ---------------------------------------------------------------------------

def _stream_creatures(url: str, only_cmcs: list | None = None) -> dict:
    """Download bulk data and stream-parse it, keeping only creature cards.

    Uses ijson to iterate one card at a time so the Pi Zero's 512 MB RAM
    is never overwhelmed by the ~300 MB JSON blob.
    """
    logger.info("Downloading and parsing bulk card data (stream mode)...")
    by_cmc: dict[int, list] = {}
    total_seen = total_kept = 0

    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        r.raw.decode_content = True  # decompress gzip on the fly
        for card in ijson.items(r.raw, "item"):
            total_seen += 1
            if total_seen % 5000 == 0:
                logger.info("  Scanned %d cards, kept %d creatures so far...", total_seen, total_kept)

            type_line = card.get("type_line") or ""
            if "Creature" not in type_line:
                continue
            if card.get("digital", False):
                continue

            # Resolve art_crop: normal card or first face of a DFC
            image_uris = card.get("image_uris") or {}
            if not image_uris.get("art_crop"):
                faces = card.get("card_faces") or []
                if faces:
                    image_uris = faces[0].get("image_uris") or {}
                if not image_uris.get("art_crop"):
                    continue

            cmc = int(card.get("cmc") or 0)
            if only_cmcs and cmc not in only_cmcs:
                continue

            mana_cost = card.get("mana_cost") or ""
            if not mana_cost:
                faces = card.get("card_faces") or []
                mana_cost = faces[0].get("mana_cost", "") if faces else ""

            oracle_text = card.get("oracle_text") or ""
            if not oracle_text:
                faces = card.get("card_faces") or []
                oracle_text = faces[0].get("oracle_text", "") if faces else ""

            entry = {
                "id": card.get("id", ""),
                "name": card.get("name", ""),
                "mana_cost": mana_cost,
                "cmc": cmc,
                "type_line": type_line,
                "power": card.get("power"),
                "toughness": card.get("toughness"),
                "oracle_text": oracle_text,
                "image_url": image_uris["art_crop"],
                "image_path": None,
            }
            by_cmc.setdefault(cmc, []).append(entry)
            total_kept += 1

    total = sum(len(v) for v in by_cmc.values())
    logger.info("Found %d creatures across CMC %s", total, sorted(by_cmc.keys()))
    return by_cmc


# ---------------------------------------------------------------------------
# Download images
# ---------------------------------------------------------------------------

def _download_images(
    by_cmc: dict,
    data_dir: Path,
    max_per_cmc: int | None,
    dry_run: bool,
) -> dict:
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

        by_cmc[cmc] = pool

    logger.info("Images: %d downloaded, %d already existed, %d failed", dl, skipped, failed)
    return by_cmc


# ---------------------------------------------------------------------------
# Save index
# ---------------------------------------------------------------------------

def _save_index(by_cmc: dict, data_dir: Path):
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
# Token fetch (Scryfall search API — much smaller than bulk data)
# ---------------------------------------------------------------------------

def _fetch_tokens(data_dir: Path, dry_run: bool):
    """Download all unique paper tokens from Scryfall, sorted by name then P/T."""
    logger.info("Fetching token list from Scryfall...")
    tokens = []
    url = "https://api.scryfall.com/cards/search"
    params = {"q": "t:token game:paper", "unique": "cards", "order": "name"}

    while url:
        r = requests.get(url, params=params, timeout=30)
        if r.status_code == 404:
            break  # no results
        r.raise_for_status()
        data = r.json()
        for card in data.get("data", []):
            name = card.get("name", "")
            # Skip double-faced / meld tokens whose name contains "//"
            if "//" in name:
                continue
            image_uris = card.get("image_uris") or {}
            if not image_uris.get("art_crop"):
                faces = card.get("card_faces") or []
                if faces:
                    image_uris = faces[0].get("image_uris") or {}
                if not image_uris.get("art_crop"):
                    continue
            oracle_text = card.get("oracle_text") or ""
            if not oracle_text:
                faces = card.get("card_faces") or []
                oracle_text = faces[0].get("oracle_text", "") if faces else ""

            tokens.append({
                "id": card.get("id", ""),
                "name": name,
                "type_line": card.get("type_line", ""),
                "power": card.get("power"),
                "toughness": card.get("toughness"),
                "oracle_text": oracle_text,
                "image_url": image_uris["art_crop"],
                "image_path": None,
            })
        url = data.get("next_page")
        params = {}
        time.sleep(REQUEST_DELAY)

    # Sort: name, then power (numeric), then toughness
    def _sort_key(t):
        try:
            p = int(t["power"]) if t["power"] else 0
        except (ValueError, TypeError):
            p = 0
        try:
            tgh = int(t["toughness"]) if t["toughness"] else 0
        except (ValueError, TypeError):
            tgh = 0
        return (t["name"].lower(), p, tgh)

    tokens.sort(key=_sort_key)

    # Deduplicate: keep first occurrence of each (name, power, toughness) triple.
    # Scryfall returns the same token printed in multiple sets; we only want one entry.
    seen: set[tuple] = set()
    deduped = []
    for t in tokens:
        key = (t["name"].lower(), t["power"], t["toughness"])
        if key not in seen:
            seen.add(key)
            deduped.append(t)
    removed = len(tokens) - len(deduped)
    tokens = deduped
    logger.info("Found %d tokens after dedup (removed %d duplicates)", len(tokens), removed)

    # Download images
    token_dir = data_dir / "tokens"
    token_dir.mkdir(parents=True, exist_ok=True)
    dl = skipped = failed = 0

    for token in tokens:
        dest = token_dir / f"{token['id']}.jpg"
        token["image_path"] = str(dest)

        if dest.exists():
            skipped += 1
            continue
        if dry_run:
            continue

        try:
            r = requests.get(token["image_url"], timeout=30)
            r.raise_for_status()
            dest.write_bytes(r.content)
            dl += 1
        except Exception as exc:
            logger.warning("  FAILED %s: %s", token["name"], exc)
            token["image_path"] = None
            failed += 1

        time.sleep(REQUEST_DELAY)

    logger.info("Token images: %d downloaded, %d existed, %d failed", dl, skipped, failed)

    if not dry_run:
        valid = [
            {k: v for k, v in t.items() if k != "image_url"}
            for t in tokens
            if t.get("image_path") and Path(t["image_path"]).exists()
        ]
        index_path = data_dir / "tokens.json"
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(valid, f, indent=2)
        logger.info("Saved token index: %d tokens -> %s", len(valid), index_path)


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
    p.add_argument("--tokens-only", action="store_true",
                   help="Only fetch tokens, skip creature cards")
    p.add_argument("--no-tokens", action="store_true",
                   help="Skip token fetch")
    args = p.parse_args()

    try:
        if not args.tokens_only:
            url = _get_bulk_url()
            by_cmc = _stream_creatures(url, only_cmcs=args.cmc)
            by_cmc = _download_images(by_cmc, args.data_dir, args.max_per_cmc, args.dry_run)
            if not args.dry_run:
                _save_index(by_cmc, args.data_dir)

        if not args.no_tokens:
            _fetch_tokens(args.data_dir, args.dry_run)

        logger.info("Done.")
    except KeyboardInterrupt:
        logger.info("Interrupted — partial index may exist.")
        sys.exit(1)
    except Exception as exc:
        logger.error("Fatal: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
