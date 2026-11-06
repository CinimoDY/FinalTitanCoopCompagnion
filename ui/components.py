"""Reusable view pieces outside the fight screen. The fight screen uses presentation.render."""
from __future__ import annotations

import html
import re
from collections.abc import Callable

import streamlit as st

from finaltitan.i18n import LANGS, NAMES
from ui import images, session


def label(text: str) -> None:
    st.markdown(f'<p class="ft-label">{html.escape(text)}</p>', unsafe_allow_html=True)


# Confirmation before a running game is abandoned. A button's on_click asks (sets the kind), the page renders the
# dialog on that run, and the dialog's primary button performs the page's action. The kind is cleared on every exit
# (confirm, cancel, dismiss, page change) so the dialog never comes back by itself.

def ask_confirm(kind: str) -> None:
    st.session_state.confirm = kind


def confirm_dialog(actions: dict[str, Callable[[], None]]) -> None:
    """Shows the dialog if this page's kind was asked for. actions: kind -> the function that abandons the game."""
    ss = st.session_state
    kind = ss.get("confirm")
    if kind not in actions:
        return
    tr = session.translator()
    clear = lambda: ss.update(confirm=None)  # noqa: E731

    def body() -> None:
        state = session.game()
        if state is not None:
            st.write(tr("confirm.body", fight=state.fight_no, defeated=len(state.defeated), total=state.total))
            st.download_button(tr("confirm.save"), session.to_json(), file_name="final-titan-coop-save.json",
                               mime="application/json", key="confirm_save")
        go, keep = st.columns(2)
        # The browser keeps a dialog open until the script reruns from inside it, so both buttons end with st.rerun()
        # (a page switch inside the action also ends the run).
        if go.button(tr(f"confirm.{kind}"), type="primary", key="confirm_go", width="stretch"):
            clear()
            actions[kind]()
            st.rerun()
        if keep.button(tr("confirm.cancel"), key="confirm_cancel", width="stretch"):
            clear()
            st.rerun()

    st.dialog(tr("confirm.title"), on_dismiss=clear)(body)()


TAKEN_ARROW = (
    '<div class="ft-taken-arrow" aria-hidden="true"><svg viewBox="0 0 100 120">'
    '<polygon points="33,8 67,8 67,60 90,60 50,112 10,60 33,60" transform="translate(7 7)" fill="#000" '
    'stroke="#000" stroke-width="7" stroke-linejoin="round"/>'
    '<polygon points="33,8 67,8 67,60 90,60 50,112 10,60 33,60" fill="#FFD400" '
    'stroke="#000" stroke-width="7" stroke-linejoin="round"/>'
    '<rect x="40" y="15" width="8" height="44" rx="3" fill="#FFF4A8"/>'
    '</svg></div>'
)


def card_image(path, width: int = 700, gray: bool = False, arrow: bool = False) -> None:
    data = images.thumb(path, width, gray)
    if data is None:
        st.caption(session.tr("common.no_image"))
    else:
        st.image(data, width="stretch")
    if arrow:
        st.markdown(TAKEN_ARROW, unsafe_allow_html=True)



# Speech balloon: a stretchable outline plus a fixed-size tail whose fill covers the outline where they join.
_BUBBLE_BODY = "M50,0 C84,-1 100,9 100,50 C100,91 84,101 50,100 C16,101 0,91 0,50 C0,9 16,-1 50,0 Z"
_BUBBLE_TAIL = (
    '<svg class="ft-bubble-tail" viewBox="0 0 42 34" aria-hidden="true">'
    '<path d="M47,0 C31,12 15,24 1,32 C17,31 33,28 47,25 Z" fill="#FFFDF4"/>'
    '<path d="M40,4.5 C29,13 15,24 1,32 C17,31 30,28.5 40,26" fill="none" stroke="#000" stroke-width="3" '
    'stroke-linejoin="round" stroke-linecap="round"/></svg>'
)


def _pop_words(text: str, start: int = 0) -> str:
    """Wraps each word in a span numbered for the staggered pop-in; <b>...</b> runs stay bold."""
    out = []
    for i, part in enumerate(re.split(r"<b>(.*?)</b>", text)):
        for word in part.split():
            span = f'<span class="w" style="--i:{start}">{word}</span>'
            out.append(f"<b>{span}</b>" if i % 2 else span)
            start += 1
    return " ".join(out)


def speech_bubble(title: str, body: str) -> None:
    title_words = len(title.split())
    st.markdown(
        '<div class="ft-bubble" role="note"><div class="ft-bubble-in">'
        f'<svg class="ft-bubble-body" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">'
        f'<path d="{_BUBBLE_BODY}" vector-effect="non-scaling-stroke"/></svg>{_BUBBLE_TAIL}'
        f'<div class="ft-bubble-text"><div class="ft-bubble-title">{_pop_words(html.escape(title))}</div>'
        f'{_pop_words(body, title_words)}</div></div></div>',
        unsafe_allow_html=True,
    )

# Comic flags: a waving outline with an offset ink shadow and a thick black stroke. The bands follow the wave.
_WAVE = "M6,10 C36,0 66,20 114,8 L114,71 C66,83 36,63 6,73 Z"
_FLAG_ART = {
    "de": (
        '<path d="M6,10 C36,0 66,20 114,8 L114,29 C66,41 36,21 6,31 Z" fill="#111"/>'
        '<path d="M6,31 C36,21 66,41 114,29 L114,50 C66,62 36,42 6,52 Z" fill="#E63946"/>'
        '<path d="M6,52 C36,42 66,62 114,50 L114,71 C66,83 36,63 6,73 Z" fill="#FFD400"/>'
    ),
    "en": (
        '<rect x="0" y="0" width="120" height="84" fill="#1D3A8A"/>'
        '<path d="M6,4 L114,80 M6,80 L114,4" stroke="#fff" stroke-width="14"/>'
        '<path d="M6,4 L114,80 M6,80 L114,4" stroke="#E63946" stroke-width="5"/>'
        '<path d="M60,0 V84 M0,42 H120" stroke="#fff" stroke-width="22"/>'
        '<path d="M60,0 V84 M0,42 H120" stroke="#E63946" stroke-width="12"/>'
    ),
}


def flag_svg(code: str) -> str:
    clip = f"ft-flag-clip-{code}"
    return (
        f'<svg class="ft-flag" viewBox="0 0 126 92" role="img" aria-label="{html.escape(NAMES[code])}">'
        f'<defs><clipPath id="{clip}"><path d="{_WAVE}"/></clipPath></defs>'
        f'<path d="{_WAVE}" transform="translate(6 6)" fill="#000"/>'
        f'<g clip-path="url(#{clip})">{_FLAG_ART[code]}</g>'
        '<path d="M14,16 C38,8 62,24 104,14" fill="none" stroke="#fff" stroke-opacity=".55" stroke-width="4" stroke-linecap="round"/>'
        f'<path d="{_WAVE}" fill="none" stroke="#000" stroke-width="5" stroke-linejoin="round"/>'
        '</svg>'
    )


def language_picker(prefix: str, width: int = 72) -> None:
    """One clickable comic flag per language: the current one in color, the others greyed out."""
    current = session.lang()
    with st.container(key=f"{prefix}_langs", horizontal=True, width="content"):
        for code in LANGS:
            state = "on" if code == current else "off"
            with st.container(key=f"{prefix}_lang_{code}_{state}", width=width):
                st.markdown(f'{flag_svg(code)}<span class="ft-flag-name">{html.escape(NAMES[code])}</span>',
                            unsafe_allow_html=True)
                st.button(NAMES[code], key=f"{prefix}_langbtn_{code}", on_click=session.set_lang, args=(code,),
                          help=session.tr("lang.label"))
