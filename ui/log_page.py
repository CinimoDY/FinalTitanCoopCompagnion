"""Log page: event log, undo, save and load, run statistics."""
from __future__ import annotations

import streamlit as st

from ui import session


def render() -> None:
    session.init()
    ss, tr = st.session_state, session.translator()
    st.title(tr("logpage.title"))
    state = session.game()
    if state is None:
        st.info(tr("common.no_game"))
        up = st.file_uploader(tr("logpage.load_save"), type="json", key="log_upload")
        if up is not None and st.button(tr("common.load"), key="log_load_empty"):
            err = session.load_json(up.getvalue())
            if err:
                st.error(err)
            else:
                session.go("arena")
        return

    c1, c2, c3 = st.columns([1, 1, 2])
    c1.button(tr("logpage.undo"), on_click=session.undo, disabled=not ss.events, key="undo_log")
    c2.download_button(tr("logpage.save"), session.to_json(), file_name="final-titan-coop-save.json", mime="application/json")
    with c3.expander(tr("logpage.load_expander"), key="log_load_expander"):
        up = st.file_uploader(tr("common.save_file"), type="json", key="log_upload2")
        if up is not None and st.button(tr("common.load"), key="log_load"):
            err = session.load_json(up.getvalue())
            if err:
                st.error(err)
            else:
                st.rerun()

    s1, s2, s3, s4 = st.columns(4)
    s1.metric(tr("logpage.fight"), state.fight_no)
    s2.metric(tr("logpage.enemies_defeated"), f"{len(state.defeated)} / {state.total}")
    s3.metric(tr("logpage.titans_left"), f"{state.player_titans_left} / {state.player_titans_total}")
    s4.metric(tr("logpage.events"), len(ss.events))

    st.subheader(tr("logpage.heading"))
    for entry in reversed(state.log):
        prefix = "↳ " if entry.kind == "hint" else f"{entry.index}. "
        st.markdown(f"{prefix}{session.text(entry.msg)}")
