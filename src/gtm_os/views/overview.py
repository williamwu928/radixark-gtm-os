from __future__ import annotations
import pandas as pd
import streamlit as st
from sqlalchemy import select, func
from ..models import Account, AccountProduct, Rank, ImportRun
from .. import config
from . import kpis, empty, segments, go_account


def render(s):
    st.markdown("# Overview")
    st.markdown('<p class="sub">Counts describe the account register, not the market. Researched and landscape-sourced accounts are counted separately.</p>', unsafe_allow_html=True)
    segs = segments(s)
    accs = list(s.scalars(select(Account)))
    researched = [a for a in accs if a.origin == "Researched"]
    landscape = [a for a in accs if a.origin != "Researched"]
    ranked = s.scalar(select(func.count(func.distinct(Rank.account_id))).where(Rank.rubric_version == config.RUBRIC_VERSION)) or 0
    last_snap = s.scalar(select(func.max(ImportRun.snapshot_date)).where(ImportRun.source.in_(["huggingface", "github"]), ImportRun.status == "ok"))
    kpis([
        (len(researched), "Accounts · researched", False),
        (len(landscape) or "Pending import", "Accounts · LF AI & Data and MAD", not landscape),
        (sum(1 for a in accs if a.relationship_status != "Unset"), "Relationship status set", False),
        (ranked or "Not computed", f"Ranked · rubric {config.RUBRIC_VERSION}" + (f" · {last_snap}" if last_snap else ""), not ranked),
        (sum(1 for a in accs if a.owner), "Owned accounts", False),
        (sum(1 for a in accs if a.next_action), "Next actions open", False),
    ])

    st.markdown("## A · Value chain (register coverage)")
    cols = st.columns(len(segs))
    for col, seg in zip(cols, segs.values()):
        n = sum(1 for a in accs if a.segment_id == seg.id)
        with col:
            if st.button(f"**{n}**  \n{seg.name}", key=f"seg_{seg.id}", use_container_width=True):
                st.session_state["acc_filter_segment"] = seg.id
                st.session_state["view"] = "Accounts"
                st.rerun()
    prod_counts = dict(s.execute(select(AccountProduct.product_id, func.count()).group_by(AccountProduct.product_id)).all())
    st.markdown(" ".join(f'<span class="pill prod">{p} · {prod_counts.get(p, 0)} accounts</span>' for p in config.PRODUCTS)
                + ' <span class="note">Select a segment to filter Accounts.</span>', unsafe_allow_html=True)

    st.markdown("## B · Segment × origin coverage")
    rows = []
    for seg in segs.values():
        r = {"Segment": seg.name}
        for o in ["Researched", "LF AI & Data", "MAD"]:
            r[o] = sum(1 for a in accs if a.segment_id == seg.id and a.origin == o)
        r["Status set"] = sum(1 for a in accs if a.segment_id == seg.id and a.relationship_status != "Unset")
        rows.append(r)
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    st.markdown(f"## C · Scale × Proximity per segment (rubric {config.RUBRIC_VERSION})")
    if not ranked:
        empty("Ranks not computed yet", "Run the signal snapshots from Research → Signals. Each segment then gets a 2×2 of Scale against Proximity with counts per quadrant.")
    else:
        rk = {}
        for r in s.scalars(select(Rank).where(Rank.rubric_version == config.RUBRIC_VERSION)):
            rk.setdefault(r.account_id, {})[r.kind] = r
        rows = []
        for seg in segs.values():
            q = {"hi/hi": 0, "hi/lo": 0, "lo/hi": 0, "lo/lo": 0}
            for a in accs:
                if a.segment_id != seg.id or a.id not in rk:
                    continue
                sc, px = rk[a.id].get("scale"), rk[a.id].get("proximity")
                hs = sc is not None and sc.rank <= max(1, sc.of // 2)
                hp = px is not None and px.score >= 2
                q[("hi" if hs else "lo") + "/" + ("hi" if hp else "lo")] += 1
            rows.append({"Segment": seg.name, "High scale · high proximity": q["hi/hi"], "High scale · low proximity": q["hi/lo"],
                         "Low scale · high proximity": q["lo/hi"], "Low scale · low proximity": q["lo/lo"]})
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        st.markdown('<p class="note">High scale = top half of the segment\'s Scale rank. High proximity = two or more proximity inputs present.</p>', unsafe_allow_html=True)

    st.markdown("## D · Next actions")
    due = sorted([a for a in accs if a.next_action], key=lambda a: (a.next_action_due or pd.Timestamp.max.date(), a.name))[:12]
    for a in due:
        c1, c2, c3, c4 = st.columns([3, 5, 2, 2])
        with c1:
            if st.button(a.name, key=f"na_{a.id}", type="tertiary"):
                go_account(a.id)
        c2.write(a.next_action)
        c3.write(a.owner or "Unassigned")
        c4.write(str(a.next_action_due) if a.next_action_due else "—")
