import re
import string

import pytest

from finaltitan import i18n
from finaltitan.catalog import load_catalog
from finaltitan.engine import initial_state, reduce
from finaltitan.events import act
from finaltitan.guide import GuidanceSettings, _texts, guide
from finaltitan.i18n import LANGS, msg, pick_lang, render, t
from finaltitan.setup import GameSetup, build_enemy, load_presets
from presentation import fx, render as view
from presentation.fx_layer import texts


def fields(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_every_language_has_the_same_keys_and_placeholders():
    en = i18n.strings("en")
    for lang in LANGS:
        other = i18n.strings(lang)
        assert set(other) == set(en), (lang, set(other) ^ set(en))
        for key, text in en.items():
            assert fields(other[key]) == fields(text), (lang, key)


def _guide_texts(spec):
    yield "short", spec.get("short")
    yield "why", spec.get("why")
    for label, _kind, _args in spec.get("primary", []):
        yield "primary", label
    for title, _path in spec.get("refs", []):
        yield "ref", title


def test_every_guide_text_exists_in_every_language():
    for step, spec in _texts()["steps"].items():
        for name, value in _guide_texts(spec):
            if isinstance(value, dict):
                assert set(value) == set(LANGS), (step, name)
                assert fields(value["de"]) == fields(value["en"]), (step, name)
            else:
                assert not value, (step, name)  # plain text only for empty fields
        for name in ("lines", "confirms"):
            if name in spec:
                assert set(spec[name]) == set(LANGS), (step, name)
                assert len(spec[name]["de"]) == len(spec[name]["en"]), (step, name)


def test_fx_words_and_taunts_exist_in_every_language():
    cfg = fx.config()
    for lang in LANGS:
        assert set(cfg["words"][lang]) == set(cfg["words"]["en"])
        assert set(cfg["taunts"][lang]) == set(cfg["taunts"]["en"])
    assert fx.damage_word(5, "de") == "KA-WUMM!"
    assert fx.taunt("whiff", 0, "de") != fx.taunt("whiff", 0, "en")


@pytest.mark.parametrize("locale, lang", [("de-DE", "de"), ("de_AT", "de"), ("DE", "de"), ("en-US", "en"),
                                          ("fr-FR", "en"), ("", "en"), (None, "en")])
def test_pick_lang_follows_the_locale_with_english_fallback(locale, lang):
    assert pick_lang(locale) == lang


def test_missing_texts_fall_back_to_english_then_to_the_key():
    assert t("setup.continue", "xx") == "Continue to draft"
    assert t("no.such.key", "de") == "no.such.key"


def test_messages_render_nested_params_per_language():
    m = msg("log.damage", name="Hydra", dmg=3, steps=[msg("step.base", n=4), msg("step.armor", n=1)])
    assert render(m, "en") == "Hydra takes 3 damage (base 4, -1 Armor)."
    assert render(m, "de") == "Hydra erleidet 3 Schaden (Grundwert 4, -1 Rüstung)."


def test_user_text_with_braces_is_never_formatted():
    assert render(msg("log.note", text="{name} {0}"), "de") == "Notiz: {name} {0}"


def _game():
    cat = load_catalog()
    s = GameSetup(players=1, difficulty="Easy", seed=2)
    s.player_titans = [t.id for t in cat.titans.values() if t.enemy_usable][:3]
    build_enemy(s, cat, load_presets())
    actions = [act("begin_game"), act("set_starter", side="players"), act("damage", base=2)]
    return reduce(initial_state(s, cat), actions)


def test_the_same_game_log_renders_in_both_languages():
    state = _game()
    en = [render(e.msg, "en") for e in state.log]
    de = [render(e.msg, "de") for e in state.log]
    assert en[0] == "Game begins." and de[0] == "Das Spiel beginnt."
    assert any("enters the arena as enemy Champion" in line for line in en)
    assert any("betritt die Arena als gegnerischer Champion" in line for line in de)
    assert not any(re.search(r"\{\w+\}", line) for line in en + de)


def test_guide_and_hud_follow_the_language():
    state = _game()
    g_de = guide(state, GuidanceSettings(level="Beginner", lang="de"))
    assert g_de.actor_label == "SPIELER"
    assert any("Euer Zug" in line for line in g_de.lines)
    assert [p.label for p in g_de.primary] == ["Unseren Zug beenden"]
    assert all("When a card" not in h for h in g_de.hints)
    assert "EUER ZUG" in view.hud_center_html(state, "de")
    assert "YOUR TURN" in view.hud_center_html(state, "en")
    assert "erleidet" in view.ticker_html(state, "de")


def test_overlay_texts_are_translated():
    de, en = texts("de"), texts("en")
    assert set(de) == set(en)
    assert de["final_fight"] == "LETZTER KAMPF" and en["final_fight"] == "FINAL FIGHT"
    assert de["token.poison"] == "Gift" and de["slash"] == "SCHWING!"


# Terms from assets/Final Titan Terminology Database - TERMINOLOGY.csv that must not appear in German texts.
WRONG_GERMAN = re.compile(
    r"Tempo|TMP|[Mm]arker|Aufladung|Teamkraft|Gesegnet|Verflucht|Angriffstabelle|ÜBERSPRINGEN|\bLeben\b|"
    r"aufgehoben|Schaden zufügen|Beim-Aufdecken|volles Leben|\b(?:einen|diesen|euren|den|dem|seinen) Titanen\b"
)


def _german_texts():
    yield from i18n.strings("de").values()
    cfg = fx.config()
    for table in (cfg["words"]["de"], cfg["taunts"]["de"]):
        for value in table.values():
            yield from (value.values() if isinstance(value, dict) else value if isinstance(value, list) else [value])
    for spec in _texts()["steps"].values():
        for value in (spec.get("short"), spec.get("why")):
            if isinstance(value, dict):
                yield value["de"]
        for name in ("lines", "confirms"):
            if name in spec:
                yield from spec[name]["de"]
        for label, _k, _a in spec.get("primary", []):
            yield label["de"]
        for title, _path in spec.get("refs", []):
            yield title["de"]


def test_german_texts_use_the_official_terminology():
    bad = [(m.group(), text) for text in _german_texts() if (m := WRONG_GERMAN.search(str(text)))]
    assert not bad, bad
