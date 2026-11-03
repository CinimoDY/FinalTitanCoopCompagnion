"""Catalog editor: card image next to its metadata, with validation."""
from __future__ import annotations

import copy

import streamlit as st

from finaltitan.catalog import save_catalog, validate
from ui import images, session


def _save(cat) -> None:
    save_catalog(cat)
    st.cache_resource.clear()
    st.toast(session.tr("cat.saved"))


def render() -> None:
    session.init()
    tr = session.translator()
    session.back_button("back_catalog")
    st.title(tr("cat.title"))
    if not session.debug():
        st.info(tr("cat.debug_only"))
        return
    if "edit_catalog" not in st.session_state:
        st.session_state.edit_catalog = copy.deepcopy(session.catalog())
    cat = st.session_state.edit_catalog

    issues = validate()
    if issues:
        with st.expander(tr("cat.issues", n=len(issues)), expanded=False, key="ed_issues"):
            for i in issues:
                st.write(f"- {i}")
    else:
        st.success(tr("cat.ok"))

    st.session_state.setdefault("ed_kind", "Titans")
    kind = st.segmented_control(tr("cat.card_type"), ["Titans", "Upgrades"], key="ed_kind",
                                format_func=lambda v: tr(f"opt.{v}")) or "Titans"
    cards = list(cat.titans.values() if kind == "Titans" else cat.upgrades.values())
    if not cards:
        st.info(tr("cat.no_cards"))
        return
    idx_key = f"ed_idx_{kind}"
    idx = min(st.session_state.get(idx_key, 0), len(cards) - 1)

    n1, n2, n3 = st.columns([1, 1, 6])
    if n1.button(tr("cat.prev"), disabled=idx == 0, key="ed_prev"):
        idx -= 1
    if n2.button(tr("cat.next"), disabled=idx >= len(cards) - 1, key="ed_next"):
        idx += 1
    st.session_state[idx_key] = idx
    card = cards[idx]
    n3.caption(f"{idx + 1} / {len(cards)} · {card.id}")

    left, right = st.columns([3, 2])
    with left:
        images.show(card.image, 640)
    with right:
        key = f"{kind}_{card.id}"
        card.name = st.text_input(tr("cat.name"), card.name, key=f"{key}_name")
        card.expansion = st.text_input(tr("cat.expansion"), card.expansion, key=f"{key}_exp")
        if kind == "Titans":
            card.name_de = st.text_input(tr("cat.name_de"), card.name_de, key=f"{key}_name_de")
            card.max_life = int(st.number_input(tr("cat.max_life"), 0, 99, card.max_life, key=f"{key}_life"))
            card.speed = int(st.number_input(tr("cat.speed"), 0, 99, card.speed, key=f"{key}_spd"))
            card.armor = int(st.number_input(tr("cat.armor"), 0, 20, card.armor, key=f"{key}_arm"))
            card.team_power = st.checkbox(tr("cat.team_power"), card.team_power, key=f"{key}_tp")
            card.legendary_id = st.text_input(tr("cat.legendary_id"), card.legendary_id, key=f"{key}_leg")
        else:
            card.legendary = st.checkbox(tr("cat.legendary"), card.legendary, key=f"{key}_legend")
        card.advanced = st.checkbox(tr("cat.advanced"), card.advanced, key=f"{key}_adv")
        card.enemy_usable = st.checkbox(tr("cat.enemy_usable"), card.enemy_usable, key=f"{key}_enemy")
        st.button(tr("cat.save"), type="primary", on_click=_save, args=(cat,))
