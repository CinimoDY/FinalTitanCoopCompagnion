"""Rules coach: guide(state, settings) -> Guidance. No Streamlit imports."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import yaml

from .catalog import DATA_DIR
from .i18n import DEFAULT, msg, render, text
from .i18n import t as tr
from .state import GameState

LEVELS = ["Beginner", "Expert"]


@dataclass
class GuidanceSettings:
    level: str = "Beginner"
    lang: str = DEFAULT


@dataclass
class PrimaryAction:
    label: str
    kind: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class Guidance:
    step: str
    actor_kind: str  # enemy | players | all
    actor_label: str
    lines: list[str] = field(default_factory=list)
    why: str = ""
    refs: list[tuple[str, str]] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    primary: list[PrimaryAction] = field(default_factory=list)
    confirms: list[str] = field(default_factory=list)  # Beginner: one button per line before the last


@lru_cache(maxsize=1)
def _load_texts(mtime: float) -> dict[str, Any]:
    with open(DATA_DIR / "guide.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _texts() -> dict[str, Any]:
    return _load_texts((DATA_DIR / "guide.yaml").stat().st_mtime)


class _Ctx(dict):
    def __missing__(self, key: str) -> str:
        return ""


def text_list(raw: Any, lang: str) -> list[str]:
    """A list of texts, given either as {lang: [...]} or as a list of {lang: text} items."""
    if isinstance(raw, dict):
        raw = raw.get(lang) or raw.get(DEFAULT) or []
    return [text(item, lang) for item in raw]


def _fmt(raw: Any, ctx: dict[str, Any], lang: str) -> str:
    return text(raw, lang).format_map(_Ctx(ctx)).strip()


def step_of(state: GameState) -> str:
    if state.phase == "start":
        return "setup"
    if state.phase in ("victory", "defeat"):
        return state.phase
    if state.phase == "fight_start":
        return "fight_start_champion" if state.enemy_role == "champion" else "fight_start_challenger"
    if state.phase == "cleanup":
        return f"cleanup_{state.result.reason}" if state.result else "cleanup_both_defeated"
    if state.active_side == "players":
        return "players_turn"
    return "enemy_turn"


def _name(state: GameState, card_id: str | None) -> str:
    if not card_id:
        return ""
    t = state.find(card_id)
    if t is not None:
        return t.name
    return next((t.name for t in state.deck if t.card_id == card_id), card_id)


def _next_line(state: GameState, lang: str) -> str:
    if state.player_titans_left == 0 or state.enemy_remaining() == 0:
        return ""
    reveal = "guide.reveal_one"
    if state.upgrade_hand and state.enemy_remaining() == 1 and len(state.upgrade_hand) > 1:
        reveal = "guide.reveal_all"
    elif not state.upgrade_hand:
        reveal = "guide.reveal_none"
    key = "guide.next_challenger" if state.arena is not None else "guide.next_enemy"
    return tr(key, lang, reveal=tr(reveal, lang))


def _context(state: GameState, lang: str) -> dict[str, Any]:
    t = state.arena
    ctx: dict[str, Any] = {"left": state.player_titans_left, "total": state.player_titans_total}
    if state.result is not None:
        ctx["enemy"] = state.result.enemy_name or _name(state, state.result.enemy_id)
        if state.result.legendary:
            ctx["legendary_line"] = tr("guide.legendary_line", lang)
    if t is not None:
        ctx["enemy"] = t.name
        ctx["speed"] = t.speed
        actions = 1 + t.statuses.action
        ctx["actions"] = actions
        ctx["action_word"] = tr("word.action" if actions == 1 else "word.actions", lang)
        ctx["roll_line"] = tr("guide.roll_app", lang, actions=actions)
        bc = t.statuses.blessed_cursed
        if bc in ("blessed", "cursed"):
            ctx["dice_line"] = tr(f"guide.dice_{bc}", lang)
    if state.phase == "cleanup":
        ctx["next_line"] = _next_line(state, lang)
    return ctx


def _hints(state: GameState, lang: str) -> list[str]:
    hints = list(state.hints)
    t = state.arena
    if t is not None and state.phase == "combat":
        if t.statuses.power:
            hints.append(msg("hint.enemy_power", n=t.statuses.power))
        if t.armor:
            hints.append(msg("hint.enemy_armor", armor=t.armor))
    for b in state.bench:
        if b.team_power:
            hints.append(msg("hint.team_power", name=b.name))
    if state.phase in ("fight_start", "combat") and state.enemy_remaining() == 1:
        hints.append(msg("hint.final_fight"))
    hints.append(msg("hint.card_wins"))
    return [render(h, lang) for h in hints]


def guide(state: GameState, settings: GuidanceSettings) -> Guidance:
    step = step_of(state)
    spec = _texts()["steps"][step]
    kind = spec.get("actor", "all")
    lang = settings.lang
    g = Guidance(step=step, actor_kind=kind, actor_label=tr(f"actor.{kind}", lang))
    g.primary = [PrimaryAction(text(label, lang), k, dict(args or {})) for label, k, args in spec.get("primary", [])]
    ctx = _context(state, lang)

    if settings.level == "Expert":
        short = _fmt(spec["short"], ctx, lang)
        g.lines = [short] if short else []
        return g
    g.lines = [line for line in (_fmt(raw, ctx, lang) for raw in text_list(spec["lines"], lang)) if line]
    g.confirms = text_list(spec.get("confirms", []), lang)
    g.why = _fmt(spec.get("why", ""), ctx, lang)
    g.refs = [(text(a, lang), b) for a, b in spec.get("refs", [])]
    g.hints = _hints(state, lang)
    return g
