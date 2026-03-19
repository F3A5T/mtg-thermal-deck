"""Local card-DB helpers for draft — set list and booster generation."""

import random

_DRAFT_SET_TYPES = {"expansion", "core", "draft_innovation", "masters", "funny"}


def get_set_list(card_manager) -> list:
    """Return draft-suitable sets available in the local DB, sorted by name."""
    return [
        s for s in card_manager.get_set_list()
        if s.get("set_type") in _DRAFT_SET_TYPES and s.get("card_count", 0) >= 80
    ]


def get_set_cards(set_code: str, card_manager) -> list:
    """Return all local cards for a set, formatted for draft use."""
    cards = card_manager.get_cards_by_set(set_code)
    result = []
    for c in cards:
        if not c.image_path:
            continue
        result.append({
            "id": c.id,
            "name": c.name,
            "image_url": f"/card-image/{c.id}",
            "rarity": c.rarity,
            "mana_cost": c.mana_cost,
            "type_line": c.type_line,
            "colors": c.colors,
            "cmc": c.cmc,
        })
    return result


def generate_booster(set_code: str, card_manager) -> list:
    """Generate a 15-card booster pack from local DB cards for a set."""
    cards = get_set_cards(set_code, card_manager)

    by_rarity: dict[str, list] = {
        "common": [], "uncommon": [], "rare": [], "mythic": [],
    }
    for card in cards:
        r = card["rarity"]
        if r in by_rarity:
            by_rarity[r].append(card)

    pack = []

    # 1 rare or mythic (1 in 8 chance of mythic)
    if by_rarity["mythic"] and (not by_rarity["rare"] or random.random() < 0.125):
        pack.append(random.choice(by_rarity["mythic"]))
    elif by_rarity["rare"]:
        pack.append(random.choice(by_rarity["rare"]))
    elif by_rarity["mythic"]:
        pack.append(random.choice(by_rarity["mythic"]))

    # 3 uncommons
    unc_pool = [c for c in by_rarity["uncommon"] if c not in pack]
    pack.extend(random.sample(unc_pool, min(3, len(unc_pool))))

    # Commons to fill to 15
    com_pool = [c for c in by_rarity["common"] if c not in pack]
    needed = 15 - len(pack)
    pack.extend(random.sample(com_pool, min(needed, len(com_pool))))

    # Fallback: pad from any card if rarities are sparse
    all_pool = [c for c in cards if c not in pack]
    random.shuffle(all_pool)
    while len(pack) < 15 and all_pool:
        pack.append(all_pool.pop())

    return pack[:15]


def generate_sealed_pool(set_code: str, card_manager) -> list:
    """Generate a sealed pool: 6 boosters + 1 bonus rare/mythic from the set."""
    pool = []
    pool_ids: set[str] = set()

    for _ in range(6):
        for card in generate_booster(set_code, card_manager):
            pool.append(card)
            pool_ids.add(card["id"])

    # Bonus rare/mythic not already in the pool
    bonus_candidates = [
        c for c in get_set_cards(set_code, card_manager)
        if c["rarity"] in ("rare", "mythic") and c["id"] not in pool_ids
    ]
    if bonus_candidates:
        pool.append(random.choice(bonus_candidates))

    return pool
