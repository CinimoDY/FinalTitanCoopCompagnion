"""Final Titan Co-op Companion: entry point and navigation."""
import streamlit as st

from presentation.theme import inject_theme
from ui import arena_page, catalog_editor, draft_page, log_page, session, setup_page

st.set_page_config(page_title="Final Titan Co-op", page_icon="🗿", layout="wide")
session.init()
inject_theme()

pages = {
    "setup": st.Page(setup_page.render, title=session.tr("nav.setup"), icon="⚙", url_path="setup", default=True),
    "draft": st.Page(draft_page.render, title=session.tr("nav.draft"), icon="🃏", url_path="draft"),
    "arena": st.Page(arena_page.render, title=session.tr("nav.arena"), icon="⚔", url_path="arena"),
    "log": st.Page(log_page.render, title=session.tr("nav.log"), icon="📜", url_path="log"),
}
if session.debug():
    pages["catalog"] = st.Page(catalog_editor.render, title=session.tr("nav.catalog"), icon="🗂", url_path="catalog")
st.session_state.pages = pages

st.navigation(list(pages.values()), position="hidden").run()
