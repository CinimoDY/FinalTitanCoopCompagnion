"""Pure reducer for the enemy side: apply(state, action) -> state. No Streamlit imports."""
from __future__ import annotations

import copy
from collections.abc import Callable

from . import events as ev
from .catalog import Catalog
from .combat import damage_pipeline, prevention, start_of_turn_damage
from .events import Action
from .i18n import Msg, msg
from .setup import GameSetup
from .state import COUNT_TOKENS, EnemyTitan, FightResult, GameState, LogEntry, Reveal

FIGHT_END_REASONS = ("enemy_defeated", "player_defeated", "both_defeated", "enemy_returned", "player_returned")


# ---------------------------------------------------------------- construction

def _enemy(catalog: Catalog, card_id: str) -> EnemyTitan:
    c = catalog.titans[card_id]
    return EnemyTitan(
        card_id=c.id, name=c.name, max_life=c.max_life, base_speed=c.speed,
        base_armor=c.armor, team_power=c.team_power, legendary_id=c.legendary_id,
    )


def initial_state(setup: GameSetup, catalog: Catalog) -> GameState:
    n = setup.player_titan_count()
    return GameState(
        seed=setup.seed, player_titans_total=n, player_titans_left=n,
        deck=[_enemy(catalog, cid) for cid in setup.enemy_titans],
        upgrade_hand=list(setup.enemy_upgrades), total=len(setup.enemy_titans),
    )


def reduce(initial: GameState, actions: list[Action]) -> GameState:
    state = copy.deepcopy(initial)
    for a in actions:
        apply_inplace(state, a)
    return state


def apply(state: GameState, action: Action) -> GameState:
    new = copy.deepcopy(state)
    apply_inplace(new, action)
    return new


def apply_inplace(state: GameState, action: Action) -> None:
    state.hints = []
    state.last_reveals = []
    state.event_count += 1
    handler = HANDLERS.get(action.kind)
    if handler is None:
        _log(state, "log.unknown_action", kind=action.kind)
        return
    handler(state, **action.args)
    for h in state.hints:
        state.log.append(LogEntry(state.event_count, h, "hint"))


# --------------------------------------------------------------------- helpers

def _log(state: GameState, key: str, **params) -> None:
    state.log.append(LogEntry(state.event_count, msg(key, **params)))


def _hint(state: GameState, key: str, **params) -> None:
    state.hints.append(msg(key, **params))


def _reveal_to_bench(state: GameState) -> None:
    if not state.deck:
        return
    t = state.deck.pop(0)
    if t.legendary_id:
        t.legendary_upgrade = t.legendary_id
    state.bench.append(t)
    state.last_reveals.append(Reveal("titan", t.card_id, "bench"))
    _log(state, "log.revealed_bench", name=t.name)


def _enter_arena(state: GameState, role: str) -> None:
    if not state.bench:
        _reveal_to_bench(state)
    if not state.bench:
        return
    t = state.bench.pop(0)
    t.life = t.max_life
    t.charged = False
    state.arena = t
    state.enemy_role = role  # type: ignore[assignment]
    # A Titan revealed to the bench and moved into the arena at once is reported only once.
    state.last_reveals = [r for r in state.last_reveals if not (r.kind == "titan" and r.card_id == t.card_id)]
    state.last_reveals.append(Reveal("titan", t.card_id, "arena"))
    _log(state, "log.enters_arena", name=t.name, role=msg(f"role.{role}"))
    if not state.bench:
        _reveal_to_bench(state)


def _reveal_upgrades(state: GameState) -> None:
    if not state.upgrade_hand:
        state.new_upgrades = []
        return
    if state.enemy_remaining() == 1:
        revealed = list(state.upgrade_hand)
        state.upgrade_hand.clear()
        if len(revealed) > 1:
            _hint(state, "hint.final_all_upgrades")
    else:
        revealed = [state.upgrade_hand.pop(0)]
    state.active_upgrades += revealed
    state.new_upgrades = revealed
    for up in revealed:
        state.last_reveals.append(Reveal("upgrade", up))
    _log(state, "log.upgrades_revealed", count=len(revealed))


def _reset_turn(state: GameState) -> None:
    state.active_side = None
    state.turn_started = False


# ----------------------------------------------------------------- fight flow

def begin_game(state: GameState) -> None:
    if state.phase != "start":
        return
    _log(state, "log.game_begins")
    _enter_arena(state, "champion")
    _reveal_upgrades(state)
    state.phase = "fight_start"


def set_starter(state: GameState, side: str) -> None:
    if state.phase != "fight_start" or state.arena is None or side not in ("enemy", "players"):
        return
    state.phase = "combat"
    state.active_side = side  # type: ignore[assignment]
    state.turn_started = side == "players"
    _log(state, f"log.combat_begins_{side}")
    if side == "enemy":
        start_turn(state)


def start_turn(state: GameState) -> None:
    t = state.arena
    if state.phase != "combat" or state.active_side != "enemy" or state.turn_started or t is None:
        return
    state.turn_no += 1
    st = t.statuses
    dmg = start_of_turn_damage(st.poison, st.fire)
    if dmg:
        source = "both" if st.poison and st.fire else "poison" if st.poison else "fire"
        t.life = max((t.life or 0) - dmg, 0)
        _log(state, f"log.tick_{source}", name=t.name, dmg=dmg, poison=st.poison, fire=st.fire)
        _hint(state, "hint.tick_ignores")
        if st.fire:
            st.fire += 1
            _hint(state, "hint.fire_grows", fire=st.fire)
    else:
        _log(state, "log.enemy_turn_starts", name=t.name)
    if (t.life or 0) <= 0:
        _end_fight(state, "enemy_defeated")
        return
    state.turn_started = True


def end_turn(state: GameState) -> None:
    if state.phase != "combat" or state.active_side is None:
        return
    ending = state.active_side
    _log(state, f"log.turn_ends_{ending}")
    state.active_side = "players" if ending == "enemy" else "enemy"
    state.turn_started = state.active_side == "players"
    if state.active_side == "players":
        state.turn_no += 1
    else:
        start_turn(state)


# --------------------------------------------------------------------- damage

def damage(state: GameState, base: int = 0, bonus: int = 0, cancel: bool = False, replacement: int | None = None) -> None:
    t = state.arena
    if t is None or not state.in_fight():
        _log(state, "log.damage_ignored")
        return
    calc = damage_pipeline(base, 0, bonus, cancel, t.armor, replacement)
    life = t.life or 0
    final, used = prevention(calc.final, life, t.statuses.dodge, t.statuses.minion)
    steps: list[Msg] = [msg("step.base", n=base)]
    if bonus:
        steps.append(msg("step.bonus", n=f"{bonus:+d}"))
    if cancel:
        steps.append(msg("step.canceled"))
    if calc.armor_reduced:
        steps.append(msg("step.armor", n=calc.armor_reduced))
        _hint(state, "hint.armor_reduced", armor=t.armor, before=calc.after_cancel, after=calc.after_armor)
    if replacement is not None:
        steps.append(msg("step.replaced", n=replacement))
    if used == "dodge":
        t.statuses.dodge -= 1
        _hint(state, "hint.dodge_used", name=t.name)
    elif used == "minion":
        t.statuses.minion -= 1
        _hint(state, "hint.minion_used", name=t.name)
    t.life = max(life - final, 0)
    _log(state, "log.damage", name=t.name, dmg=final, steps=steps)
    if t.life <= 0:
        _end_fight(state, "enemy_defeated")


def heal(state: GameState, amount: int) -> None:
    t = state.arena
    if t is None or t.life is None:
        return
    before = t.life
    t.life = min(t.max_life, t.life + max(amount, 0))
    _log(state, "log.heal", name=t.name, amount=t.life - before)


def life_adjust(state: GameState, delta: int) -> None:
    t = state.arena
    if t is None or t.life is None or not state.in_fight():
        return
    t.life = max(0, min(t.max_life, t.life + delta))
    _log(state, "log.life_adjust", name=t.name, delta=f"{delta:+d}", life=t.life)
    if t.life <= 0:
        _end_fight(state, "enemy_defeated")


# --------------------------------------------------------------------- tokens

def token(state: GameState, target: str, token: str, delta: int) -> None:
    t = state.find(target)
    if t is None:
        return
    st = t.statuses
    if token in ("blessed", "cursed"):
        if delta > 0:
            if st.blessed_cursed == "none":
                st.blessed_cursed = token  # type: ignore[assignment]
            elif st.blessed_cursed == token:
                _hint(state, "hint.token_already", name=t.name, token=msg(f"token.{token}"))
            else:
                _hint(state, "hint.token_opposite", name=t.name, token=msg(f"token.{st.blessed_cursed}"))
                st.blessed_cursed = "none"
        elif st.blessed_cursed == token:
            st.blessed_cursed = "none"
    elif token in COUNT_TOKENS:
        before = getattr(st, token)
        setattr(st, token, max(0, before + delta))
    else:
        return
    _log(state, "log.token", name=t.name, token=msg(f"token.{token}"), delta=f"{delta:+d}")


def flag(state: GameState, target: str, flag: str, value: bool) -> None:
    t = state.find(target)
    if t is None or flag not in ("charged", "ultimate_form"):
        return
    setattr(t, flag, bool(value))
    _log(state, f"log.flag_{'on' if value else 'off'}", name=t.name, flag=msg(f"flag.{flag}"))


def speed(state: GameState, value: int | None) -> None:
    t = state.arena
    if t is None:
        return
    t.speed_override = value
    _log(state, "log.speed", name=t.name, speed=t.speed)


# ------------------------------------------------------------ fight endings

def _end_fight(state: GameState, reason: str) -> None:
    t = state.arena
    if t is None or reason not in FIGHT_END_REASONS:
        return
    winner = {"enemy_defeated": "players", "enemy_returned": "players", "player_defeated": "enemy",
              "player_returned": "enemy"}.get(reason)
    result = FightResult(reason=reason, winner=winner, enemy_id=t.card_id)  # type: ignore[arg-type]
    if reason in ("enemy_defeated", "both_defeated"):
        result.legendary = t.legendary_upgrade
        state.defeated.append(t.card_id)
        state.arena = None
        state.enemy_role = None
        _log(state, "log.enemy_defeated", name=t.name)
    elif reason == "enemy_returned":
        t.life = None
        t.charged = False
        t.statuses.fire = 0
        state.bench.insert(0, t)
        state.arena = None
        state.enemy_role = None
        _hint(state, "hint.enemy_returned")
        _log(state, "log.enemy_returned", name=t.name)
    else:
        t.statuses.fire = 0
        t.charged = False
        state.enemy_role = "champion"
        _log(state, "log.enemy_wins_fight", name=t.name)
    if reason in ("player_defeated", "both_defeated"):
        state.player_titans_left = max(state.player_titans_left - 1, 0)
        _log(state, "log.player_defeated", left=state.player_titans_left)
    if reason == "both_defeated":
        _hint(state, "hint.both_defeated")
    state.result = result
    _reset_turn(state)
    if state.player_titans_left == 0:
        state.phase = "defeat"
        _log(state, "log.defeat")
    elif state.enemy_remaining() == 0:
        state.phase = "victory"
        _log(state, "log.victory")
    else:
        state.phase = "cleanup"


def fight_end(state: GameState, reason: str) -> None:
    if not state.in_fight():
        return
    _end_fight(state, reason)


def swap(state: GameState, with_id: str) -> None:
    t = state.arena
    incoming = next((b for b in state.bench if b.card_id == with_id), None)
    if t is None or incoming is None or not state.in_fight():
        return
    idx = state.bench.index(incoming)
    t.life = None
    t.charged = False
    t.statuses.fire = 0
    state.bench[idx] = t
    incoming.life = incoming.max_life
    incoming.charged = False
    state.arena = incoming
    _log(state, "log.swap", name=t.name, other=incoming.name)
    _hint(state, "hint.swap")


def advance_fight(state: GameState) -> None:
    if state.phase != "cleanup" or state.result is None:
        return
    result = state.result
    if result.reason != "enemy_returned":
        _reveal_upgrades(state)
    else:
        state.new_upgrades = []
    if state.arena is None:
        # A player Titan holds the arena unless both fighters fell.
        role = "champion" if result.reason == "both_defeated" else "challenger"
        _enter_arena(state, role)
    elif not state.bench:
        _reveal_to_bench(state)
    state.phase = "fight_start"
    state.fight_no += 1
    state.result = None
    _reset_turn(state)


def add_enemy_upgrade(state: GameState, card_id: str) -> None:
    state.upgrade_hand.append(card_id)
    _log(state, "log.upgrade_added")


def note(state: GameState, text: str) -> None:
    _log(state, "log.note", text=text)


HANDLERS: dict[str, Callable[..., None]] = {
    ev.BEGIN_GAME: begin_game,
    ev.SET_STARTER: set_starter,
    ev.START_TURN: start_turn,
    ev.END_TURN: end_turn,
    ev.DAMAGE: damage,
    ev.HEAL: heal,
    ev.LIFE_ADJUST: life_adjust,
    ev.TOKEN: token,
    ev.FLAG: flag,
    ev.SPEED: speed,
    ev.FIGHT_END: fight_end,
    ev.SWAP: swap,
    ev.ADD_ENEMY_UPGRADE: add_enemy_upgrade,
    ev.NOTE: note,
    ev.ADVANCE_FIGHT: advance_fight,
}
