"""Sealed deck routes."""

from flask import Blueprint, current_app, jsonify, render_template, request

sealed_bp = Blueprint("sealed", __name__, url_prefix="/sealed")


@sealed_bp.route("/")
def index():
    return render_template("sealed.html")


@sealed_bp.route("/api/open", methods=["POST"])
def api_open():
    from app.draft.local_db import generate_sealed_pool, get_set_list
    data = request.get_json(silent=True) or {}
    set_code = data.get("set_code", "").strip().lower()
    if not set_code:
        return jsonify({"error": "set_code is required"}), 400
    cm = current_app.card_manager  # type: ignore[attr-defined]
    pool = generate_sealed_pool(set_code, cm)
    if not pool:
        return jsonify({"error": "No cards found for this set"}), 404
    return jsonify({"pool": pool})


@sealed_bp.route("/api/sets")
def api_sets():
    from app.draft.local_db import get_set_list
    cm = current_app.card_manager  # type: ignore[attr-defined]
    return jsonify(get_set_list(cm))
