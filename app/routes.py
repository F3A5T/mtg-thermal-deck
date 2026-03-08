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


@bp.route("/api/reload", methods=["POST"])
def api_reload():
    """Reload card index from disk (after running fetch_cards.py)."""
    current_app.card_manager.reload()  # type: ignore[attr-defined]
    return jsonify({"ok": True})
