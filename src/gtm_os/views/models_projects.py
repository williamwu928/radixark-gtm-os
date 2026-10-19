from __future__ import annotations
import pandas as pd
import streamlit as st
from sqlalchemy import select, func
from ..models import ModelRecord, Project, Account, ImportRun
from . import empty, go_account


def render(s):
    st.markdown("# Models & Projects")
    st.markdown('<p class="sub">Model publishers and serving providers from the Hugging Face snapshot; projects from the LF AI & Data landscape and GitHub.</p>', unsafe_allow_html=True)
    t1, t2, t3 = st.tabs(["Models", "Projects", "Serving-provider mappings"])
    names = dict(s.execute(select(Account.id, Account.name)).all())
    with t1:
        models = list(s.scalars(select(ModelRecord).order_by(ModelRecord.downloads_30d.desc().nullslast()).limit(500)))
        if not models:
            empty("No models yet", "Run the Hugging Face snapshot from Research → Signals. Accounts need a Hugging Face org (set via aliases) to be covered.")
        else:
            q = st.text_input("Filter models", placeholder="model id or publisher")
            rows = [{"Model": m.id, "Publisher": names.get(m.publisher_account_id, m.hf_org), "Modality": m.modality or "", "30-day downloads": m.downloads_30d,
                     "Likes": m.likes, "Providers": m.providers or "", "SGLang supported": "Yes" if m.sglang_supported else ("No" if m.sglang_supported is not None else "Unknown"),
                     "Published": str(m.created) if m.created else "", "Snapshot": str(m.snapshot_date)} for m in models
                    if not q or q.lower() in m.id.lower() or q.lower() in (names.get(m.publisher_account_id, m.hf_org) or "").lower()]
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    with t2:
        projects = list(s.scalars(select(Project).order_by(Project.role, Project.name)))
        q = st.text_input("Filter projects", placeholder="name, category or org")
        rows = [{"id": p.id, "Project": p.name, "Role": p.role or "", "Category": p.category or "", "Backing account": names.get(p.account_id, "") if p.account_id else "",
                 "GitHub org": p.github_org or "", "Hosting": p.hosting or "", "Stars": p.stars, "Repo": p.repo_url or ""} for p in projects
                if not q or q.lower() in f"{p.name} {p.category} {p.github_org}".lower()]
        ev = st.dataframe(pd.DataFrame(rows).drop(columns=["id"]) if rows else pd.DataFrame(), hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row")
        if ev and ev.selection and ev.selection.rows:
            p = projects[[x["id"] for x in rows].index(rows[ev.selection.rows[0]]["id"])] if False else s.get(Project, rows[ev.selection.rows[0]]["id"])
            if p.account_id:
                go_account(p.account_id)
        st.markdown('<p class="note">Projects link to a backing account only on an exact alias, domain or GitHub-org match. Unlinked projects can be attached from the account page later.</p>', unsafe_allow_html=True)
    with t3:
        models = list(s.scalars(select(ModelRecord).where(ModelRecord.providers != None)))  # noqa: E711
        if not models:
            empty("No provider mappings yet", "Filled by the Hugging Face snapshot: which inference providers serve which published models.")
        else:
            rows = {}
            for m in models:
                for p in (m.providers or "").split(","):
                    if p:
                        r = rows.setdefault(p, {"Provider": p, "Models served": 0, "SGLang-supported models": 0})
                        r["Models served"] += 1
                        r["SGLang-supported models"] += 1 if m.sglang_supported else 0
            st.dataframe(pd.DataFrame(sorted(rows.values(), key=lambda r: -r["Models served"])), hide_index=True, use_container_width=True)
