"""GTM-OS-IC: one account intelligence and opportunity workflow."""
from __future__ import annotations
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
import pandas as pd
import streamlit as st
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gtm_os.db import Account, Opportunity, ModelRecord, session
from gtm_os.services.importer import bootstrap
from gtm_os.services import opportunities as crm

st.set_page_config(page_title="GTM-OS-IC", page_icon="▣", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>
.block-container{padding-top:2rem;padding-bottom:2rem}
h1{font-size:1.65rem!important} h3{font-size:1.05rem!important}
div[data-testid="stDataFrame"]{border:1px solid #e5e7eb;border-radius:8px}
</style>""", unsafe_allow_html=True)


def gate():
    password = os.environ.get("APP_PASSWORD")
    if password and not st.session_state.get("authed"):
        st.title("GTM-OS-IC")
        with st.form("login"):
            given = st.text_input("Team password", type="password")
            if st.form_submit_button("Sign in"):
                if given == password:
                    st.session_state.authed = True
                    st.rerun()
                else: st.error("That password does not match.")
        st.stop()


@st.cache_resource
def boot():
    bootstrap()
    crm.initialize()


def link(url):
    if url and urlparse(url).scheme in {"http", "https"}:
        st.link_button("Open source", url)


def detail(aid):
    if st.button("← Accounts"):
        st.session_state.pop("acct", None)
        st.session_state.pop("account_id", None)
        st.session_state["table_version"] = st.session_state.get("table_version", 0) + 1
        st.rerun()
    with session() as s:
        a = s.get(Account, aid)
        if a is None:
            st.warning("Account not found.")
            return
        o = s.get(Opportunity, aid)
        d = dict(o.details or {}) if o else {}
        st.title(a.name)
        stage = o.stage if o else "Research"
        st.markdown(f'<span style="color:{crm.COLORS[stage]};font-weight:600">● {stage}</span>', unsafe_allow_html=True)
        with st.expander("Source research & recorded relationships"):
            st.caption("Source records are preserved. An opportunity hypothesis does not establish a customer or partner relationship.")
            st.write("Original category:", a.source_category or (a.segment.name if a.segment else "Unclassified"))
            for n in a.notes:
                st.write(n.text)
                st.caption(f"{n.date} · {n.source.title if n.source else 'Research note'}")
                link(n.source_url)
            for c in a.contacts:
                st.write(f"{c.name} · {c.title or ''} · {c.buying_role or ''}")
            for activity in a.activities[:10]:
                st.write(f"{activity.date} · {activity.type} · {activity.summary}")
            models = list(s.scalars(select(ModelRecord).where(ModelRecord.publisher_account_id == aid)))
            if models: st.write("Recorded models:", ", ".join(m.id for m in models))
            if not a.notes: st.caption("No sourced research recorded yet.")
        with st.form(f"edit-{aid}"):
            st.subheader("Company & Technical Profile")
            left, right = st.columns(2)
            name = left.text_input("Account name", a.name)
            icp = right.selectbox("ICP category", crm.SEGMENTS, index=crm.SEGMENTS.index(o.icp_segment if o else crm.segment_for(a)))
            website = left.text_input("Website", a.homepage or "")
            d["subcategory"] = right.text_input("Subcategory", d.get("subcategory", ""))
            d["description"] = left.text_area("Business description", d.get("description", ""), height=80)
            workload = right.text_area("Technical workload", o.workload if o else "", height=80)
            d["stack"] = left.text_area("Known models, engines, clouds or hardware", d.get("stack", ""), height=80)
            d["source_links"] = right.text_area("Additional source links", d.get("source_links", ""), height=80)
            st.subheader("Commercial Opportunity")
            hypothesis = st.text_area("Opportunity hypothesis", o.hypothesis if o else "", height=85)
            c1, c2, c3 = st.columns(3)
            typ = c1.selectbox("Opportunity type", [""] + crm.TYPES, index=([""] + crm.TYPES).index(o.opportunity_type if o else ""))
            new_stage = c2.selectbox("Stage", crm.STAGES, index=crm.STAGES.index(stage))
            basis = c3.selectbox("Basis", ["Hypothesis", "Evidence-backed"], index=0 if not o or o.basis == "Hypothesis" else 1)
            left, right = st.columns(2)
            d["problem"] = left.text_area("Expected customer problem", d.get("problem", ""), height=80)
            d["solution"] = right.text_area("Proposed solution or partnership", d.get("solution", ""), height=80)
            evidence = st.text_area("Trigger / Evidence", o.evidence if o else "", help="Include source links. Keep proposed discovery separate from verified buying signals.", height=80)
            st.subheader("Buyer & Relationships")
            left, right = st.columns(2)
            d["contact"] = left.text_input("Relevant contact", d.get("contact", ""))
            d["job_title"] = right.text_input("Job title", d.get("job_title", ""))
            d["buyer_role"] = left.text_input("Technical champion / economic buyer role", d.get("buyer_role", ""))
            d["warm_path"] = right.text_input("Possible introduction path", d.get("warm_path", ""))
            d["relationship_notes"] = st.text_area("Relationship notes", d.get("relationship_notes", ""), height=80)
            st.subheader("Execution")
            left, right = st.columns(2)
            owner = left.text_input("Owner", a.owner or "")
            due = right.date_input("Due date", value=a.next_action_due)
            action = st.text_area("Next action", a.next_action or d.get("suggested_action", ""), height=80)
            d["latest_activity"] = st.text_input("Latest activity", d.get("latest_activity", ""))
            d["notes"] = st.text_area("Notes", d.get("notes", ""), height=80)
            if st.form_submit_button("Save", type="primary"):
                try:
                    crm.save(aid, name=name, website=website, owner=owner, next_action=action, due=due,
                        segment=icp, workload=workload, hypothesis=hypothesis, opportunity_type=typ,
                        stage=new_stage, basis=basis, evidence=evidence, details=d)
                except ValueError as exc: st.error(str(exc))
                else:
                    st.session_state["saved"] = True
                    st.rerun()
    if st.session_state.pop("saved", False): st.success("Saved")


def accounts():
    st.title("GTM-OS-IC")
    st.caption("Account Intelligence & Opportunity Tracker")
    c1, c2, c3, c4 = st.columns([3, 2, 1.5, 1.5])
    query = c1.text_input("Search", placeholder="Company or opportunity", key="search")
    segment = c2.selectbox("ICP segment", [""] + crm.SEGMENTS, format_func=lambda x: x or "All segments")
    typ = c3.selectbox("Opportunity type", [""] + crm.TYPES, format_func=lambda x: x or "All types")
    stage = c4.selectbox("GTM stage", [""] + crm.STAGES, format_func=lambda x: x or "All stages")
    c1, c2 = st.columns([2, 6])
    sort = c1.selectbox("Sort by", ["Account", "ICP Segment", "Stage", "Due Date"])
    show_due = c2.checkbox("Show due dates")
    data = crm.rows(query, segment, typ, stage, sort)
    st.caption(f"{len(data):,} accounts · Select a row to review evidence and edit")
    st.markdown(" · ".join(f'<span style="color:{color}">● {label}</span>' for label, color in crm.COLORS.items()), unsafe_allow_html=True)
    if not data:
        st.info("No accounts match these filters.")
        return
    df = pd.DataFrame(data).drop(columns=["id"] + ([] if show_due else ["Due Date"]))
    styled = df.style.map(lambda value: f"color: {crm.COLORS[value]}; font-weight: bold", subset=["Stage"])
    event = st.dataframe(styled, hide_index=True, width="stretch", height=550,
        on_select="rerun", selection_mode="single-row", key=f"table-{query}-{segment}-{typ}-{stage}-{sort}-{st.session_state.get('table_version', 0)}",
        column_config={"Opportunity": st.column_config.TextColumn(width="large"), "Trigger / Evidence": st.column_config.TextColumn(width="medium")})
    if event.selection.rows:
        st.session_state["acct"] = data[event.selection.rows[0]]["id"]
        st.rerun()
    with st.expander("Open an account"):
        aid = st.selectbox("Account", [r["id"] for r in data], format_func={r["id"]: r["Account"] for r in data}.get)
        if st.button("Open account"):
            st.session_state["acct"] = aid
            st.rerun()


gate()
boot()
account_id = st.session_state.get("acct") or st.session_state.get("account_id")
if account_id: detail(account_id)
else: accounts()
