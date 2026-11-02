"""The enemy die. The app draws the faces; it never applies them. No Streamlit imports."""
from __future__ import annotations

import random
from dataclasses import dataclass
from functools import lru_cache

import yaml

from .catalog import DATA_DIR
from .i18n import Msg, msg
from .state import GameState


@dataclass(frozen=True)
class Face:
    id: str
    kind: str  # chart | charge | miss
    column: int | None = None  # Attack Chart column of a chart face


@lru_cache(maxsize=1)
def faces() -> tuple[Face, ...]:
    with open(DATA_DIR / "dice.yaml", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)["faces"]
    return tuple(Face(f["id"], f["kind"], f.get("column")) for f in raw)


def face(face_id: str) -> Face | None:
    return next((f for f in faces() if f.id == face_id), None)


def roll(count: int = 1, rng: random.Random | None = None) -> list[str]:
    """`count` independent uniform draws, as face ids."""
    rng = rng or random.SystemRandom()
    return [rng.choice(faces()).id for _ in range(max(1, min(int(count), 2)))]


def slots(state: GameState) -> int:
    """Enemy Actions this turn: 1 + Action tokens + Actions gained by flipping Charge."""
    t = state.arena
    return 1 + (t.statuses.action if t else 0) + state.turn_extra_actions


def roll_hint(state: GameState) -> Msg | None:
    """What the latest roll of this enemy turn asks the players to do. Only a pointer; nothing is applied."""
    t = state.arena
    if t is None or not state.turn_rolls:
        return None
    r = state.turn_rolls[-1]
    if r.pending:
        return msg("roll.pick_enemy" if r.token == "blessed" else "roll.pick_players")
    if not r.faces:
        return msg("roll.table_done")
    if r.doubles:
        return msg("roll.doubles", token=msg(f"token.{r.token}"))
    f = face(r.result or "")
    if f is None:
        return None
    if f.kind == "charge":
        return msg("roll.result_ultimate" if t.charged else "roll.result_charge")
    if f.kind == "miss":
        return msg("roll.result_miss")
    return msg("roll.result_chart", face=msg(f"die.{f.id}"))
