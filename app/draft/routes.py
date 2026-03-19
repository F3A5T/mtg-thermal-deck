"""Flask routes for the draft feature."""

import threading

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for

from .local_db import get_set_list
from .session import create_session, get_session

draft_bp = Blueprint("draft", __name__, url_prefix="/draft")


def _session_or_404(session_id: str):
    s = get_session(session_id)
    if not s:
        return None, (jsonify({"error": "Session not found"}), 404)
    return s, None


# ------------------------------------------------------------------
# Pages
# ------------------------------------------------------------------

@draft_bp.route("/")
def lobby():
    return render_template("draft/index.html")


@draft_bp.route("/<session_id>")
def room(session_id):
    session, err = _session_or_404(session_id)
    if err:
        return render_template("draft/index.html", error="Room not found.")
    return render_template("draft/room.html", session=session.lobby_view())


@draft_bp.route("/<session_id>/seat/<int:seat_index>")
def seat(session_id, seat_index):
    session, err = _session_or_404(session_id)
    if err:
        return render_template("draft/index.html", error="Room not found.")
    if seat_index < 0 or seat_index >= session.num_seats:
        return redirect(url_for("draft.room", session_id=session_id))
    session.join_seat(seat_index)
    return render_template(
        "draft/seat.html",
        session_id=session_id,
        seat_index=seat_index,
        set_name=session.set_name,
        num_seats=session.num_seats,
    )


@draft_bp.route("/<session_id>/pool/<int:seat_index>")
def pool(session_id, seat_index):
    session, err = _session_or_404(session_id)
    if err:
        return render_template("draft/index.html", error="Room not found.")
    export = session.export_list(seat_index)
    seat = session.seats[seat_index]
    return render_template(
        "draft/pool.html",
        session_id=session_id,
        seat_index=seat_index,
        seat_name=seat.name or f"Seat {seat_index + 1}",
        set_name=session.set_name,
        picks=seat.picks,
        export=export,
    )


# ------------------------------------------------------------------
# API
# ------------------------------------------------------------------

@draft_bp.route("/api/sets")
def api_sets():
    try:
        cm = current_app.card_manager  # type: ignore[attr-defined]
        sets = get_set_list(cm)
        return jsonify(sets)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


@draft_bp.route("/api/create", methods=["POST"])
def api_create():
    data = request.get_json(silent=True) or {}
    set_code = data.get("set_code", "").strip().lower()
    set_name = data.get("set_name", set_code).strip()
    num_seats = int(data.get("num_seats", 8))
    num_seats = max(2, min(8, num_seats))

    if not set_code:
        return jsonify({"error": "set_code is required"}), 400

    cm = current_app.card_manager  # type: ignore[attr-defined]
    session = create_session(set_code, set_name, num_seats, card_manager=cm)

    # Generate packs in background; session enters "loading" state
    t = threading.Thread(target=session.generate_packs, daemon=True, name=f"draft-packs-{session.session_id}")
    t.start()

    return jsonify({"session_id": session.session_id})


@draft_bp.route("/<session_id>/api/lobby")
def api_lobby(session_id):
    session, err = _session_or_404(session_id)
    if err:
        return err
    return jsonify(session.lobby_view())


@draft_bp.route("/<session_id>/api/start", methods=["POST"])
def api_start(session_id):
    session, err = _session_or_404(session_id)
    if err:
        return err
    ok = session.start()
    if not ok:
        return jsonify({"error": "Cannot start — packs still loading or already started"}), 409
    return jsonify({"ok": True})


@draft_bp.route("/<session_id>/api/state")
def api_state(session_id):
    session, err = _session_or_404(session_id)
    if err:
        return err
    seat_index = request.args.get("seat", type=int)
    if seat_index is not None:
        return jsonify(session.seat_view(seat_index))
    return jsonify(session.lobby_view())


@draft_bp.route("/<session_id>/api/pick", methods=["POST"])
def api_pick(session_id):
    session, err = _session_or_404(session_id)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    seat_index = data.get("seat")
    card_id = data.get("card_id", "")
    if seat_index is None:
        return jsonify({"error": "seat is required"}), 400
    result = session.make_pick(int(seat_index), card_id)
    if not result.get("ok"):
        return jsonify(result), 409
    return jsonify(result)


@draft_bp.route("/<session_id>/api/export")
def api_export(session_id):
    session, err = _session_or_404(session_id)
    if err:
        return err
    seat_index = request.args.get("seat", 0, type=int)
    text = session.export_list(seat_index)
    return text, 200, {"Content-Type": "text/plain"}
