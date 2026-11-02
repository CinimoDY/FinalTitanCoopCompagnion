"""The enemy die: the app rolls it and shows the result; it never applies it (design/enemy-roll-design.md)."""
import random
from dataclasses import asdict
from pathlib import Path

import pytest

from finaltitan import dice, events as ev
from finaltitan.catalog import load_catalog
from finaltitan.engine import apply, initial_state, reduce
from finaltitan.events import act
from finaltitan.guide import GuidanceSettings, guide
from finaltitan.i18n import LANGS, render
from finaltitan.setup import GameSetup, build_enemy, load_presets
from presentation import fx, render as view
from presentation.fx_layer import payload_html

CAT = load_catalog()
FACES = ["blue", "green", "yellow", "red", "charge", "miss"]


def make_setup(seed=3):
    s = GameSetup(players=1, difficulty="Easy", seed=seed)
    s.player_titans = [t.id for t in CAT.titans.values() if t.enemy_usable][:3]
    build_enemy(s, CAT, load_presets())
    return s


def enemy_turn(*actions, setup=None):
    return reduce(initial_state(setup or make_setup(), CAT), [act(ev.BEGIN_GAME), act(ev.SET_STARTER, side="enemy"), *actions])


def roll(*faces, token="none"):
    return act(ev.ROLL, faces=list(faces), token=token)


def game_state(state):
    """Everything about the enemy that a roll must leave alone."""
    t = state.arena
    return asdict(t), state.phase, state.active_side, state.turn_started, state.player_titans_left, list(state.defeated)


# ------------------------------------------------------------------- the die

def test_the_die_has_the_six_confirmed_faces():
    assert [f.id for f in dice.faces()] == FACES
    assert [f.column for f in dice.faces() if f.kind == "chart"] == [0, 1, 2, 3]
    assert [f.kind for f in dice.faces()][4:] == ["charge", "miss"]


def test_rolls_are_uniform_valid_faces_and_seedable():
    rng = random.Random(7)
    seen = [dice.roll(1, rng)[0] for _ in range(1200)]
    assert set(seen) == set(FACES)
    assert all(seen.count(f) > 120 for f in FACES)
    assert dice.roll(2, random.Random(1)) == dice.roll(2, random.Random(1))
    assert len(dice.roll(2)) == 2 and len(dice.roll(1)) == 1 and len(dice.roll(9)) == 2


@pytest.mark.parametrize("face", FACES)
def test_every_face_has_an_image_like_the_cards(face):
    assert (Path(view.STATIC) / "dice" / f"{face}.webp").exists()
    assert face in view.dice_srcs()


# -------------------------------------------------------------------- engine

@pytest.mark.parametrize("face", FACES)
def test_a_roll_is_only_recorded_never_applied(face):
    before = enemy_turn()
    after = apply(before, roll(face))
    assert game_state(after) == game_state(before)
    assert [r.faces for r in after.turn_rolls] == [[face]]
    assert after.turn_rolls[0].result == face
    assert after.turn_extra_actions == 0 and not after.arena.charged


def test_a_roll_writes_a_log_line_in_both_languages():
    after = enemy_turn(roll("yellow"))
    entry = after.log[-1]
    assert render(entry.msg, "en") == f"{after.arena.name} rolls Yellow (Action 1)."
    assert render(entry.msg, "de") == f"{after.arena.name} würfelt Gelb (Aktion 1)."


def test_invalid_or_misplaced_rolls_are_ignored():
    state = enemy_turn()
    assert apply(state, roll("purple")).turn_rolls == []
    assert apply(state, roll("blue", "red", "green")).turn_rolls[0].faces == ["blue", "red"]  # at most two dice
    players = reduce(initial_state(make_setup(), CAT), [act(ev.BEGIN_GAME), act(ev.SET_STARTER, side="players"), roll("blue")])
    assert players.turn_rolls == []
    assert render(players.log[-1].msg, "en") == "Roll ignored: it is not the enemy's turn."
    assert reduce(initial_state(make_setup(), CAT), [roll("blue")]).turn_rolls == []


def test_undo_removes_the_roll():
    actions = [act(ev.BEGIN_GAME), act(ev.SET_STARTER, side="enemy"), roll("red")]
    assert len(reduce(initial_state(make_setup(), CAT), actions).turn_rolls) == 1
    assert reduce(initial_state(make_setup(), CAT), actions[:-1]).turn_rolls == []


def test_action_slots_count_action_tokens_and_charge_flips():
    state = enemy_turn()
    assert dice.slots(state) == 1
    arena = state.arena.card_id
    state = apply(state, act(ev.TOKEN, target=arena, token="action", delta=1))
    assert dice.slots(state) == 2
    state = apply(state, act(ev.FLAG, target=arena, flag="charged", value=True))
    assert dice.slots(state) == 3 and state.turn_extra_actions == 1
    state = apply(state, act(ev.FLAG, target=arena, flag="charged", value=False))  # the Ultimate: no extra Action
    assert dice.slots(state) == 3


def test_a_new_turn_starts_with_a_clean_tracker():
    state = enemy_turn(roll("blue"), roll("miss"))
    assert len(state.turn_rolls) == 2
    state = apply(state, act(ev.END_TURN))
    assert state.turn_rolls == []
    state = apply(state, act(ev.END_TURN))  # back to the enemy
    assert state.turn_rolls == [] and state.turn_extra_actions == 0


def test_more_rolls_than_actions_are_allowed():
    state = enemy_turn(roll("blue"), roll("blue"), roll("red"))
    assert len(state.turn_rolls) == 3 and dice.slots(state) == 1


def test_blessed_and_cursed_roll_two_dice_and_wait_for_the_pick():
    for token, who, line in (("blessed", "enemy", "The enemy picks Red."), ("cursed", "players", "The players pick Red.")):
        state = enemy_turn(act(ev.TOKEN, target=enemy_turn().arena.card_id, token=token, delta=1), roll("blue", "red", token=token))
        r = state.turn_rolls[-1]
        assert r.pending and r.result is None and r.token == token
        assert dice.roll_hint(state).key == f"roll.pick_{who}"
        state = apply(state, act(ev.ROLL_PICK, index=1))
        assert state.turn_rolls[-1].pick == 1 and state.turn_rolls[-1].result == "red"
        assert render(state.log[-1].msg, "en") == line
        assert apply(state, act(ev.ROLL_PICK, index=0)).turn_rolls[-1].pick == 1  # decided once


def test_doubles_resolve_one_die_and_never_remove_the_token():
    arena = enemy_turn().arena.card_id
    state = enemy_turn(act(ev.TOKEN, target=arena, token="blessed", delta=1), roll("green", "green", token="blessed"))
    r = state.turn_rolls[-1]
    assert r.doubles and not r.pending and r.result == "green"
    assert state.arena.statuses.blessed_cursed == "blessed"  # the players remove it with the button
    assert dice.roll_hint(state).key == "roll.doubles"
    assert [render(h, "en") for h in state.hints] == ["Doubles: resolve only one die and remove the Blessed token."]
    state = apply(state, act(ev.TOKEN, target=arena, token="blessed", delta=-1))
    assert state.arena.statuses.blessed_cursed == "none"


def test_a_roll_on_the_table_only_fills_an_action_slot():
    state = enemy_turn(roll())
    assert len(state.turn_rolls) == 1 and state.turn_rolls[0].result is None
    assert dice.roll_hint(state).key == "roll.table_done"


def test_roll_hints_point_without_applying():
    arena = enemy_turn().arena.card_id
    assert dice.roll_hint(enemy_turn(roll("yellow"))).key == "roll.result_chart"
    assert dice.roll_hint(enemy_turn(roll("miss"))).key == "roll.result_miss"
    assert dice.roll_hint(enemy_turn(roll("charge"))).key == "roll.result_charge"
    charged = enemy_turn(act(ev.FLAG, target=arena, flag="charged", value=True), roll("charge"))
    assert dice.roll_hint(charged).key == "roll.result_ultimate"
    assert dice.roll_hint(enemy_turn()) is None


# ------------------------------------------------------------------- guide

def test_guide_follows_the_dice_setting_and_language():
    state = enemy_turn()
    app = guide(state, GuidanceSettings(level="Beginner", dice="App"))
    table = guide(state, GuidanceSettings(level="Beginner", dice="Table"))
    de = guide(state, GuidanceSettings(level="Beginner", lang="de"))
    assert any("Press **Roll**" in line for line in app.lines)
    assert any("Roll one die" in line for line in table.lines)
    assert any("**Würfeln**" in line for line in de.lines)
    assert not any("{" in line for line in app.lines + table.lines + de.lines)


# --------------------------------------------------------------------- cues

def step(state, *actions):
    for a in actions:
        after = apply(state, a)
        cues = fx.cues_for(a, state, after)
        state = after
    return state, cues


def test_a_roll_throws_the_die_then_glows_the_matching_icon():
    state, cues = step(enemy_turn(), roll("yellow"))
    assert [c.kind for c in cues] == ["roll", "roll_glow"]
    throw, glow = cues
    assert throw.target == f"card-{state.arena.card_id}" == glow.target
    assert throw.params["faces"] == ["yellow"] and throw.params["word"] == "ROLL!" and not throw.params["pending"]
    icons = fx.config()["chart_icons"]
    assert glow.params["icon"] == {"x": icons["x"][2], "y": icons["y"], "r": icons["r"]}
    assert glow.params["color"] == fx.config()["die_glow"]["yellow"]
    assert not throw.blocking and not glow.blocking


@pytest.mark.parametrize("face, column", [("blue", 0), ("green", 1), ("yellow", 2), ("red", 3)])
def test_each_colored_face_lights_its_own_chart_column(face, column):
    _, cues = step(enemy_turn(), roll(face))
    icon = cues[-1].params["icon"]
    assert icon["x"] == fx.config()["chart_icons"]["x"][column]


def test_chart_icons_are_ordered_and_inside_the_card():
    icons = fx.config()["chart_icons"]
    assert icons["x"] == sorted(icons["x"]) and all(0 < x < 1 for x in icons["x"])
    assert 0 < icons["y"] < 1 and 0 < icons["r"] < 0.1


def test_charge_and_miss_get_a_hint_not_an_icon():
    arena = enemy_turn().arena.card_id
    _, cues = step(enemy_turn(), roll("charge"))
    assert "icon" not in cues[-1].params and cues[-1].params["word"] == "CHARGE!" and cues[-1].params["ultimate"] is False
    _, cues = step(enemy_turn(act(ev.FLAG, target=arena, flag="charged", value=True)), roll("charge"))
    assert cues[0].params["charged"] is True and cues[-1].params["ultimate"] is True
    _, cues = step(enemy_turn(), roll("miss"))
    assert cues[-1].params["word"] == "MISS!" and "icon" not in cues[-1].params


def test_two_dice_wait_for_the_pick_before_the_glow():
    arena = enemy_turn().arena.card_id
    base = enemy_turn(act(ev.TOKEN, target=arena, token="cursed", delta=1))
    state, cues = step(base, roll("blue", "red", token="cursed"))
    assert [c.kind for c in cues] == ["roll"]
    assert cues[0].params["pending"] and cues[0].params["token"] == "cursed" and cues[0].params["faces"] == ["blue", "red"]
    _, cues = step(state, act(ev.ROLL_PICK, index=1))
    assert [c.kind for c in cues] == ["roll_pick", "roll_glow"]
    assert cues[0].params["pick"] == 1 and cues[1].params["face"] == "red"


def test_doubles_flag_the_cue_and_glow_one_icon():
    arena = enemy_turn().arena.card_id
    base = enemy_turn(act(ev.TOKEN, target=arena, token="blessed", delta=1))
    _, cues = step(base, roll("green", "green", token="blessed"))
    assert cues[0].params["doubles"] and cues[0].params["doubles_word"] == "DOUBLES!"
    assert cues[1].params["face"] == "green"


def test_ignored_rolls_and_table_rolls_make_no_glow():
    players = reduce(initial_state(make_setup(), CAT), [act(ev.BEGIN_GAME), act(ev.SET_STARTER, side="players")])
    assert step(players, roll("blue"))[1] == []
    _, cues = step(enemy_turn(), roll())
    assert [c.kind for c in cues] == ["roll"] and cues[0].params["faces"] == []


def test_taunts_follow_the_result_and_the_language():
    _, red = step(enemy_turn(), roll("red"))
    _, miss = step(enemy_turn(), roll("miss"))
    _, blue = step(enemy_turn(), roll("blue"))
    assert red[0].params["taunt"] in fx.config()["taunts"]["en"]["roll_power"]
    assert miss[0].params["taunt"] in fx.config()["taunts"]["en"]["roll_miss"]
    assert "taunt" not in blue[0].params
    state = enemy_turn()
    a = roll("miss")
    de = fx.cues_for(a, state, apply(state, a), lang="de")
    assert de[0].params["word"] == "WÜRFEL!" and de[-1].params["word"] == "FEHLSCHLAG!"
    assert de[0].params["taunt"] in fx.config()["taunts"]["de"]["roll_miss"]


def test_roll_cues_have_durations_so_the_glow_starts_after_the_landing():
    d = fx.config()["durations"]
    assert 1200 <= d["roll"] <= 1800 and d["roll_pick"] and d["roll_glow"]


def test_overlay_payload_carries_dice_images_and_the_pending_pick():
    html = payload_html([], fx.FxSettings(), {"dice": view.dice_srcs()}, {"pending_pick": True})
    assert "app/static/dice/blue.webp" in html and '"pending_pick": true' in html
    assert "ft-die-cube" in html and "roll_glow" in html  # dice.js is part of the engine


# ------------------------------------------------------------------- render

def test_tracker_shows_actions_chips_and_empty_slots():
    arena = enemy_turn().arena.card_id
    state = enemy_turn(act(ev.TOKEN, target=arena, token="action", delta=2), roll("blue"), roll("charge"))
    html = view.roll_tracker_html(state, "en")
    assert "Action 3 of 3" in html
    assert html.count('class="ft-chip') == 3 and html.count("ft-chip slot") == 1 and html.count("big new") == 1
    assert 'src="app/static/dice/blue.webp"' in html and 'src="app/static/dice/charge.webp"' in html
    assert "\n" not in html
    assert "Aktion 3 von 3" in view.roll_tracker_html(state, "de")


def test_tracker_turns_to_done_and_counts_extra_rolls():
    state = enemy_turn(roll("blue"))
    html = view.roll_tracker_html(state, "en")
    assert "All Actions rolled" in html and "ft-tracker done" in html
    assert "+1 extra" in view.roll_tracker_html(apply(state, roll("red")), "en")


def test_tracker_marks_kept_and_dropped_dice_and_table_rolls():
    arena = enemy_turn().arena.card_id
    base = enemy_turn(act(ev.TOKEN, target=arena, token="blessed", delta=1), roll("blue", "red", token="blessed"))
    assert "kept" not in view.roll_tracker_html(base, "en")
    picked = apply(base, act(ev.ROLL_PICK, index=0))
    html = view.roll_tracker_html(picked, "en")
    assert 'class="die-blue kept"' in html and 'class="die-red dropped"' in html and "two blessed" in html
    assert "&#127922;" in view.roll_tracker_html(enemy_turn(roll()), "en")


def test_every_roll_text_exists_in_both_languages():
    from finaltitan import i18n
    keys = [k for k in i18n.strings("en") if k.startswith(("roll.", "die.", "dice.", "log.roll", "hint.doubles", "js.roll"))]
    assert len(keys) > 25
    for lang in LANGS:
        assert all(k in i18n.strings(lang) for k in keys)
