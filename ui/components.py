"""Reusable view pieces outside the fight screen. The fight screen uses presentation.render."""
from __future__ import annotations

import html

import streamlit as st

from finaltitan.i18n import LANGS, NAMES
from ui import images, session


def label(text: str) -> None:
    st.markdown(f'<p class="ft-label">{html.escape(text)}</p>', unsafe_allow_html=True)


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
