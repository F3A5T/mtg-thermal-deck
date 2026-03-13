from flask import Blueprint, current_app, jsonify, render_template, request

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    state = current_app.app_state  # type: ignore[attr-defined]
    return render_template("index.html", status=state.get_status())


@bp.route("/api/status")
def api_status():
    state = current_app.app_state  # type: ignore[attr-defined]
    return jsonify(state.get_status())


@bp.route("/api/print", methods=["POST"])
def api_print():
    state = current_app.app_state  # type: ignore[attr-defined]
    state.current_mode.handle_button("X")
    return jsonify({"ok": True})


@bp.route("/api/cmc", methods=["POST"])
def api_cmc():
    """Adjust CMC on the active mode.

    Body (JSON):
      { "action": "up" | "down" }   — increment / decrement
      { "value": <int> }            — set directly
    """
    state = current_app.app_state  # type: ignore[attr-defined]
    mode = state.current_mode
    data = request.get_json(silent=True) or {}

    if "action" in data:
        if data["action"] == "up":
            mode.handle_button("A")
        elif data["action"] == "down":
            mode.handle_button("B")
    elif "value" in data:
        from app.modes.momir import MomirMode
        if isinstance(mode, MomirMode):
            mode.cmc = max(MomirMode.MIN_CMC, min(MomirMode.MAX_CMC, int(data["value"])))
            mode.status_message = ""

    return jsonify(state.get_status())


@bp.route("/api/mode", methods=["POST"])
def api_mode():
    """Cycle to the next mode (same as pressing Y)."""
    state = current_app.app_state  # type: ignore[attr-defined]
    state.next_mode()
    return jsonify(state.get_status())


@bp.route("/api/tokens")
def api_tokens_list():
    """Return lightweight token list for the web UI (index, name, P/T).

    Used to build the letter-jump index and search filter client-side.
    Only available when a TokenMode is registered (returns [] otherwise).
    """
    from app.modes.token import TokenMode
    state = current_app.app_state  # type: ignore[attr-defined]
    for mode in state.modes:
        if isinstance(mode, TokenMode):
            return jsonify(mode.list_items())
    return jsonify([])


@bp.route("/api/token", methods=["POST"])
def api_token():
    """Navigate tokens in TokenMode.

    Body (JSON):
      { "action": "next" | "prev" | "goto", "index": <int> }
    """
    state = current_app.app_state  # type: ignore[attr-defined]
    mode = state.current_mode
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    if action == "next":
        mode.handle_button("A")
    elif action == "prev":
        mode.handle_button("B")
    elif action == "goto":
        if hasattr(mode, "goto"):
            mode.goto(int(data.get("index", 0)))
    return jsonify(state.get_status())


@bp.route("/api/life", methods=["POST"])
def api_life():
    """Adjust life totals.

    Body (JSON):
      { "action": "increment" | "decrement", "player": 0-3, "amount": <int> }
      { "action": "select", "player": 0-3 }
      { "action": "reset" }
    """
    from app.modes.life import LifeMode
    state = current_app.app_state  # type: ignore[attr-defined]
    data = request.get_json(silent=True) or {}
    action = data.get("action")

    life_mode = next((m for m in state.modes if isinstance(m, LifeMode)), None)
    if life_mode is None:
        return jsonify({"error": "LifeMode not registered"}), 404

    player = int(data.get("player", life_mode._selected))
    amount = int(data.get("amount", 1))

    if action == "increment":
        life_mode._life[player] += amount
    elif action == "decrement":
        life_mode._life[player] -= amount
    elif action == "select":
        life_mode._selected = player
    elif action == "reset":
        life_mode.reset()

    return jsonify(life_mode.get_status())


@bp.route("/api/reload", methods=["POST"])
def api_reload():
    """Reload card index from disk (after running fetch_cards.py)."""
    current_app.card_manager.reload()  # type: ignore[attr-defined]
    state = current_app.app_state  # type: ignore[attr-defined]
    from app.modes.token import TokenMode
    from app.modes.browser import CardBrowserMode
    from app.modes.decklist import DecklistMode
    for mode in state.modes:
        if isinstance(mode, TokenMode):
            mode.reload()
        elif isinstance(mode, CardBrowserMode):
            mode.on_activate()
        elif isinstance(mode, DecklistMode):
            mode.reload_tokens()
    return jsonify({"ok": True})


@bp.route("/api/hotspot", methods=["POST"])
def api_hotspot():
    """Toggle the WiFi hotspot on or off."""
    from app.modes.info import _hotspot_active, HOTSPOT_CON
    import subprocess
    data = request.get_json(silent=True) or {}
    # Optional: pass {"active": true/false} to force a state, else toggle
    want = data.get("active")
    currently = _hotspot_active()
    if want is None:
        want = not currently
    if bool(want) == currently:
        return jsonify({"ok": True, "hotspot_active": currently, "changed": False})
    try:
        if want:
            subprocess.run(
                ["sudo", "nmcli", "connection", "up", HOTSPOT_CON],
                check=True, capture_output=True,
            )
        else:
            subprocess.run(
                ["sudo", "nmcli", "connection", "down", HOTSPOT_CON],
                check=True, capture_output=True,
            )
        return jsonify({"ok": True, "hotspot_active": want, "changed": True})
    except subprocess.CalledProcessError as exc:
        return jsonify({"ok": False, "error": exc.stderr.decode(errors="replace")}), 500


# ------------------------------------------------------------------
# Decklist API
# ------------------------------------------------------------------

def _get_decklist_mode():
    from app.modes.decklist import DecklistMode
    state = current_app.app_state  # type: ignore[attr-defined]
    return next((m for m in state.modes if isinstance(m, DecklistMode)), None)


@bp.route("/api/deck/load", methods=["POST"])
def api_deck_load():
    """Fetch a deck from Moxfield or Archidekt and resolve against local DB.

    Body (JSON): { "url": "https://www.moxfield.com/decks/..." }
    Returns full deck status.
    """
    from app.decklist import load_deck_from_url

    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "url is required"}), 400

    mode = _get_decklist_mode()
    if not mode:
        return jsonify({"error": "DecklistMode not registered"}), 500

    try:
        deck_name, cards = load_deck_from_url(url)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Failed to fetch deck: {exc}"}), 502

    status = mode.load_deck(deck_name, cards)
    return jsonify(status)


@bp.route("/api/deck/status")
def api_deck_status():
    """Return current deck state."""
    mode = _get_decklist_mode()
    if not mode:
        return jsonify({"error": "DecklistMode not registered"}), 500
    return jsonify(mode.get_status())


@bp.route("/api/deck/print", methods=["POST"])
def api_deck_print():
    """Print a single card from the deck by name (all copies).

    Body (JSON): { "name": "Lightning Bolt" }
    """
    from app.decklist import PRINT_CATEGORIES

    mode = _get_decklist_mode()
    if not mode:
        return jsonify({"error": "DecklistMode not registered"}), 500

    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    art = bool(data.get("art", True))
    if not name:
        return jsonify({"error": "name is required"}), 400

    # Find the DeckCard by name
    dc = next((c for c in mode._all_cards if c.name.lower() == name.lower()), None)
    if not dc or not dc.found:
        return jsonify({"error": f"'{name}' not found in local DB"}), 404

    import threading
    result = {"ok": False}

    def _do():
        for _ in range(dc.quantity):
            result["ok"] = mode.printer.print_card(dc.card, art=art)
        mode.last_printed = f"Printed: {dc.quantity}x {dc.name}"

    t = threading.Thread(target=_do, daemon=True)
    t.start()
    t.join(timeout=60)

    return jsonify({"ok": result["ok"], "name": dc.name, "quantity": dc.quantity})


@bp.route("/api/deck/print-all", methods=["POST"])
def api_deck_print_all():
    """Start background print of the full mainboard + commanders.

    Returns immediately; poll /api/deck/status for progress.
    """
    mode = _get_decklist_mode()
    if not mode:
        return jsonify({"error": "DecklistMode not registered"}), 500
    if mode._printing:
        return jsonify({"error": "Already printing"}), 409

    data = request.get_json(silent=True) or {}
    art = bool(data.get("art", True))
    mode._trigger_print_all(art=art)
    return jsonify({"ok": True, "print_total": mode._print_total})


# ------------------------------------------------------------------
# Card Browser API  (independent of the current on-screen mode)
# ------------------------------------------------------------------

@bp.route("/api/cards")
def api_cards_list():
    """Return lightweight card list matching optional filters.

    Query params: cmc=<int>, color=W|U|B|R|G|C, type=<str>
    Returns: { total: N, cards: [{id, name, cmc, colors, type_line, power, toughness}] }
    """
    cm = current_app.card_manager  # type: ignore[attr-defined]
    cmc = request.args.get("cmc", type=int)
    color = request.args.get("color") or None
    type_kw = request.args.get("type") or None

    cards = cm.filter_cards(cmc=cmc, color=color, type_keyword=type_kw)
    return jsonify({
        "total": len(cards),
        "cards": [
            {
                "id": c.id,
                "name": c.name,
                "cmc": c.cmc,
                "colors": c.colors,
                "type_line": c.type_line,
                "power": c.power,
                "toughness": c.toughness,
            }
            for c in cards
        ],
    })


@bp.route("/api/cards/random", methods=["POST"])
def api_cards_random():
    """Pick a random card matching filters and return its full dict.

    Body (JSON): { cmc: <int|null>, color: <str|null>, type: <str|null> }
    """
    cm = current_app.card_manager  # type: ignore[attr-defined]
    data = request.get_json(silent=True) or {}
    cmc = data.get("cmc")
    if isinstance(cmc, str):
        cmc = int(cmc) if cmc.isdigit() else None
    color = data.get("color") or None
    type_kw = data.get("type") or None

    card = cm.random_card(cmc=cmc, color=color, type_keyword=type_kw)
    if not card:
        return jsonify({"error": "No cards match filters"}), 404
    return jsonify(card.to_dict())


@bp.route("/api/cards/print", methods=["POST"])
def api_cards_print():
    """Print a card by ID.

    Body (JSON): { id: <str> }
    """
    cm = current_app.card_manager  # type: ignore[attr-defined]
    printer = current_app.printer  # type: ignore[attr-defined]
    data = request.get_json(silent=True) or {}
    card_id = data.get("id", "")
    art = bool(data.get("art", True))

    card = cm.get_card_by_id(card_id)
    if not card:
        return jsonify({"error": "Card not found"}), 404

    import threading

    result = {"ok": False}

    def _do():
        result["ok"] = printer.print_card(card, art=art)

    t = threading.Thread(target=_do, daemon=True)
    t.start()
    t.join(timeout=30)

    return jsonify({"ok": result["ok"], "card": card.to_dict()})
