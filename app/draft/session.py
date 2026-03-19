"""Draft session state management."""

import threading
import time
import uuid
from dataclasses import dataclass, field

from .local_db import generate_booster

PACKS_PER_PLAYER = 3
PACK_SIZE = 15
# Pass direction per pack index: +1 = left (seat+1), -1 = right (seat-1)
_PASS_DIR = [1, -1, 1]

_sessions: dict = {}
_lock = threading.Lock()


def get_session(session_id: str):
    return _sessions.get(session_id)


def create_session(set_code: str, set_name: str, num_seats: int, card_manager=None) -> "DraftSession":
    sid = uuid.uuid4().hex[:8]
    session = DraftSession(sid, set_code, set_name, num_seats, card_manager=card_manager)
    with _lock:
        _sessions[sid] = session
    return session


def cleanup_old_sessions(max_age_hours: int = 24):
    cutoff = time.time() - max_age_hours * 3600
    with _lock:
        stale = [sid for sid, s in _sessions.items() if s.created_at < cutoff]
        for sid in stale:
            del _sessions[sid]


@dataclass
class DraftSeat:
    index: int
    name: str = ""
    joined: bool = False
    picks: list = field(default_factory=list)
    current_pack: list = field(default_factory=list)

    def to_dict(self, include_pack: bool = False) -> dict:
        d = {
            "index": self.index,
            "name": self.name or f"Seat {self.index + 1}",
            "joined": self.joined,
            "pick_count": len(self.picks),
        }
        if include_pack:
            d["current_pack"] = self.current_pack
            d["picks"] = self.picks
        return d


class DraftSession:
    def __init__(self, session_id: str, set_code: str, set_name: str, num_seats: int, card_manager=None):
        self.session_id = session_id
        self.set_code = set_code
        self.set_name = set_name
        self.num_seats = num_seats
        self.seats = [DraftSeat(i) for i in range(num_seats)]
        self.state = "lobby"  # lobby | loading | drafting | done
        self.pack_number = 0
        self.created_at = time.time()
        self._lock = threading.Lock()
        self._error: str = ""
        self._card_manager = card_manager

        # Pre-generated packs: _packs[seat][pack_num] = list of 15 cards
        self._packs: list = []

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def generate_packs(self):
        """Generate all packs for all seats. Call in a background thread."""
        try:
            self.state = "loading"
            packs = []
            for _ in range(self.num_seats):
                seat_packs = [generate_booster(self.set_code, self._card_manager) for _ in range(PACKS_PER_PLAYER)]
                packs.append(seat_packs)
            self._packs = packs
            self.state = "lobby"
        except Exception as exc:
            self._error = str(exc)
            self.state = "error"

    def join_seat(self, seat_index: int, name: str = "") -> bool:
        if seat_index < 0 or seat_index >= self.num_seats:
            return False
        seat = self.seats[seat_index]
        seat.joined = True
        if name:
            seat.name = name
        return True

    def start(self) -> bool:
        if self.state not in ("lobby",):
            return False
        if not self._packs:
            return False
        with self._lock:
            # Deal pack 0 to all seats
            for i, seat in enumerate(self.seats):
                seat.current_pack = list(self._packs[i][0])
            self.pack_number = 0
            self.state = "drafting"
        return True

    # ------------------------------------------------------------------
    # Draft mechanics
    # ------------------------------------------------------------------

    def make_pick(self, seat_index: int, card_id: str) -> dict:
        """Pick a card. Returns {ok, waiting, message}."""
        with self._lock:
            if self.state != "drafting":
                return {"ok": False, "message": "Draft not active"}

            seat = self.seats[seat_index]
            card = next((c for c in seat.current_pack if c["id"] == card_id), None)
            if card is None:
                return {"ok": False, "message": "Card not in your pack"}

            seat.current_pack.remove(card)
            seat.picks.append(card)

            # Pass remaining pack to next seat
            remaining = seat.current_pack[:]
            seat.current_pack = []

            if remaining:
                direction = _PASS_DIR[self.pack_number]
                next_seat_idx = (seat_index + direction) % self.num_seats
                # Queue the pack — next seat takes it immediately if their hand is empty
                self._give_pack(next_seat_idx, remaining)

            # Check if all seats are done picking (all current_packs empty)
            if all(len(s.current_pack) == 0 for s in self.seats):
                self._advance()

            return {"ok": True, "waiting": len(seat.current_pack) == 0}

    def _give_pack(self, seat_index: int, pack: list):
        """Give a pack to a seat. If their hand is empty, take it immediately."""
        seat = self.seats[seat_index]
        if not seat.current_pack:
            seat.current_pack = pack
        else:
            # This shouldn't normally happen in a real draft, but handle gracefully
            # by merging — in practice packs pass serially so a seat won't have two
            seat.current_pack.extend(pack)

    def _advance(self):
        """Move to the next pick round or next pack."""
        picks_per_seat = PACK_SIZE * (self.pack_number + 1)
        if all(len(s.picks) >= picks_per_seat for s in self.seats):
            # Pack done — move to next pack
            self.pack_number += 1
            if self.pack_number >= PACKS_PER_PLAYER:
                self.state = "done"
            else:
                # Deal new packs
                for i, seat in enumerate(self.seats):
                    seat.current_pack = list(self._packs[i][self.pack_number])

    # ------------------------------------------------------------------
    # State views
    # ------------------------------------------------------------------

    def seat_view(self, seat_index: int) -> dict:
        seat = self.seats[seat_index]
        return {
            "session_id": self.session_id,
            "set_name": self.set_name,
            "state": self.state,
            "pack_number": self.pack_number + 1,
            "pick_number": (len(seat.picks) % PACK_SIZE) + 1,
            "total_picks": len(seat.picks),
            "current_pack": seat.current_pack,
            "picks": seat.picks,
            "waiting": len(seat.current_pack) == 0 and self.state == "drafting",
            "other_seats": [
                {"index": s.index, "name": s.name or f"Seat {s.index+1}", "pick_count": len(s.picks)}
                for s in self.seats if s.index != seat_index
            ],
        }

    def lobby_view(self) -> dict:
        return {
            "session_id": self.session_id,
            "set_name": self.set_name,
            "set_code": self.set_code,
            "state": self.state,
            "error": self._error,
            "num_seats": self.num_seats,
            "seats": [s.to_dict() for s in self.seats],
        }

    def export_list(self, seat_index: int) -> str:
        picks = self.seats[seat_index].picks
        counts: dict[str, int] = {}
        for card in picks:
            counts[card["name"]] = counts.get(card["name"], 0) + 1
        lines = sorted(f"{qty} {name}" for name, qty in counts.items())
        return "\n".join(lines)
