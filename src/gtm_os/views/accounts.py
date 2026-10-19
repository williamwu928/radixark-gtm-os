from __future__ import annotations
from datetime import date
import pandas as pd
import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from ..models import Account, ModelRecord, Project
from ..services import crm, ranking
from .. import config
from . import segments, empty, fmt_rank, rank_detail, go_account, load_account

PAGE = 50


def render(s):
    if st.session_state.get("account_id"):
        detail(s, st.session_state["account_id"])
        return
    st.markdown("# Accounts")
    segs = segments(s)
    seg_opts = ["All segments"] + [x.name for x in segs.values()]
    seg_by_name = {x.name: x.id for x in segs.values()}
    pre = st.session_state.pop("acc_filter_segment", None)
    if pre:
        st.session_state["f_seg"] = segs[pre].name
    c = st.columns([3, 2, 2, 2, 2, 2])
    q = c[0].text_input("Search name", key="f_q", placeholder="Filter by name or domain")
    seg = c[1].selectbox("Segment", seg_opts, key="f_seg")
    origin = c[2].selectbox("Origin", ["Any origin", "Researched", "LF AI & Data", "MAD"], key="f_origin")
    status = c[3].selectbox("Relationship status", ["Any status"] + config.RELATIONSHIP_STATUSES, key="f_status")
    prod = c[4].selectbox("Product", ["Any product"] + config.PRODUCTS, key="f_prod")
    sort = c[5].selectbox("Sort", ["Scale rank", "Proximity rank", "Name", "Recently updated"], key="f_sort")

    stmt = select(Account).options(selectinload(Account.products), selectinload(Account.segment))
    if q:
        stmt = stmt.where(Account.name.ilike(f"%{q}%") | Account.domain.ilike(f"%{q}%"))
    if seg != "All segments":
        stmt = stmt.where(Account.segment_id == seg_by_name[seg])
    if origin != "Any origin":
        stmt = stmt.where(Account.origin == origin)
    if status != "Any status":
        stmt = stmt.where(Account.relationship_status == status)
    accs = list(s.scalars(stmt))
    if prod != "Any product":
        accs = [a for a in accs if any(p.product_id == prod for p in a.products)]
    rk = ranking.ranks_for(s, [a.id for a in accs])

    def key(a):
        r = rk.get(a.id, {})
        origin_order = 0 if a.origin == "Researched" else 1
        if sort == "Scale rank":
            return (origin_order, 0 if "scale" in r else 1, r["scale"].rank if "scale" in r else 0, a.name.lower())
        if sort == "Proximity rank":
            return (origin_order, 0 if "proximity" in r else 1, r["proximity"].rank if "proximity" in r else 0, a.name.lower())
        if sort == "Recently updated":
            return (-a.updated_at.timestamp(),)
        return (a.name.lower(),)
    accs.sort(key=key)
    total = len(accs)
    page = st.session_state.get("acc_page", 0)
    pages = max(1, (total + PAGE - 1) // PAGE)
    page = min(page, pages - 1)
    st.markdown(f'<p class="sub">{total} accounts · page {page + 1} of {pages}. Researched accounts sort above landscape-only accounts.</p>', unsafe_allow_html=True)
    rows = []
    for a in accs[page * PAGE:(page + 1) * PAGE]:
        r = rk.get(a.id, {})
        rows.append({"id": a.id, "Account": a.name, "Origin": a.origin, "Segment": a.segment.name, "Vertical": a.vertical or "",
                     "Products": ", ".join(p.product_id for p in a.products), "Relationship status": a.relationship_status,
                     "Scale rank": fmt_rank(r.get("scale")), "Proximity rank": fmt_rank(r.get("proximity")),
                     "Owner": a.owner or "Unassigned", "Next action": a.next_action or ""})
    df = pd.DataFrame(rows)
    ev = st.dataframe(df.drop(columns=["id"]) if rows else df, hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row", height=min(38 * (len(rows) + 1) + 4, 900))
    sel = ev.selection.rows if ev and ev.selection else []
    if sel:
        go_account(rows[sel[0]]["id"])
    p1, p2, p3 = st.columns([1, 1, 6])
    if p1.button("← Previous", disabled=page == 0):
        st.session_state["acc_page"] = page - 1; st.rerun()
    if p2.button("Next →", disabled=page >= pages - 1):
        st.session_state["acc_page"] = page + 1; st.rerun()
    p3.markdown('<p class="note">Select a row to open the account.</p>', unsafe_allow_html=True)


def detail(s, account_id: str):
    a = load_account(s, account_id)
    if a is None:
        st.session_state.pop("account_id", None); st.rerun()
    segs = segments(s)
    if st.button("← Accounts", type="tertiary"):
        st.session_state.pop("account_id", None); st.rerun()
    st.markdown(f"# {a.name}")
    parent = s.get(Account, a.parent_id) if a.parent_id else None
    badges = [a.segment.name, a.origin, f"Status: {a.relationship_status}", f"Owner: {a.owner or 'unassigned'}", f"Priority: {a.priority}"]
    st.markdown(" ".join(f'<span class="pill na">{b}</span>' for b in badges), unsafe_allow_html=True)
    tabs = st.tabs(["Overview", "Models & Stack", "Ranking", "People", "Activity"])

    with tabs[0]:
        left, right = st.columns([3, 2])
        with left:
            st.markdown("### Details")
            info = {
                "Identity": f"{a.name}" + (f" · {a.business_unit}" if a.business_unit else ""),
                "Hierarchy": f"{parent.name} (parent)" if parent else "—",
                "Homepage": a.homepage or "—", "GitHub": a.github_org or "—", "Hugging Face": a.hf_org or "—",
                "Source category": a.source_category or "—",
                "Segment fit hypothesis": a.segment.fit_hypothesis or "—",
                "Status set on": str(a.status_date) if a.status_date else "—",
                "Next action due": str(a.next_action_due) if a.next_action_due else "—",
            }
            st.table(pd.DataFrame({"Field": info.keys(), "Value": info.values()}).set_index("Field"))
            st.markdown("### Research notes")
            if not a.notes:
                empty("No research notes", "Add one on the right: a sentence, a source link, a date.")
            for n in a.notes:
                src = f'<a href="{n.source_url}" target="_blank">{n.source.title if n.source else "source"}</a>' if n.source_url else (n.source.title if n.source else "")
                st.markdown(f'<div class="rn"><div>{n.text}</div><div class="m">{src}{" · " if src else ""}{n.date}{" · " + n.author if n.author else ""}</div></div>', unsafe_allow_html=True)
        with right:
            st.markdown("### Update account")
            with st.form("acct_form"):
                status = st.selectbox("Relationship status", config.RELATIONSHIP_STATUSES, index=config.RELATIONSHIP_STATUSES.index(a.relationship_status))
                owner = st.text_input("Owner", a.owner or "")
                priority = st.selectbox("Priority", config.PRIORITIES, index=config.PRIORITIES.index(a.priority))
                seg_name = st.selectbox("Segment", [x.name for x in segs.values()], index=list(segs).index(a.segment_id))
                vertical = st.text_input("Vertical", a.vertical or "")
                prods = st.multiselect("Products", config.PRODUCTS, default=[p.product_id for p in a.products])
                next_action = st.text_input("Next action", a.next_action or "")
                due = st.date_input("Due", a.next_action_due, value=a.next_action_due) if a.next_action_due else st.date_input("Due", value=None)
                if st.form_submit_button("Save", type="primary"):
                    seg_id = [k for k, v in segs.items() if v.name == seg_name][0]
                    crm.update_account(s, a.id, relationship_status=status, owner=owner, priority=priority, segment_id=seg_id, vertical=vertical, next_action=next_action, next_action_due=due)
                    crm.set_products(s, a.id, prods)
                    st.success("Saved"); st.rerun()
            with st.form("note_form", clear_on_submit=True):
                st.markdown("**Add research note**")
                text = st.text_area("Note", height=80, label_visibility="collapsed", placeholder="What we learned")
                url = st.text_input("Source link", placeholder="https://")
                author = st.text_input("Author", placeholder="Your name")
                if st.form_submit_button("Add note") and text.strip():
                    crm.add_note(s, a.id, text, url, author); st.rerun()

    with tabs[1]:
        models = list(s.scalars(select(ModelRecord).where(ModelRecord.publisher_account_id == a.id).order_by(ModelRecord.downloads_30d.desc().nullslast())))
        projects = list(s.scalars(select(Project).where(Project.account_id == a.id)))
        if not models and not projects:
            empty("Nothing linked yet", "Models arrive with the Hugging Face snapshot (needs a Hugging Face org on the account). Projects link from the landscape import or GitHub.")
        if models:
            st.markdown("### Models (Hugging Face)")
            st.dataframe(pd.DataFrame([{"Model": m.id, "Modality": m.modality or "", "30-day downloads": m.downloads_30d, "Likes": m.likes,
                                        "Providers": m.providers or "", "SGLang supported": "Yes" if m.sglang_supported else ("No" if m.sglang_supported is not None else "Unknown"),
                                        "Snapshot": str(m.snapshot_date)} for m in models]), hide_index=True, use_container_width=True)
        if projects:
            st.markdown("### Projects")
            st.dataframe(pd.DataFrame([{"Project": p.name, "Role": p.role, "Category": p.category or "", "Repo": p.repo_url or "", "Hosting": p.hosting or ""} for p in projects]), hide_index=True, use_container_width=True)
        st.markdown("### Stack")
        st.markdown('<p class="note">Hardware / cloud and deployment mode: Unknown until recorded in a research note or activity.</p>', unsafe_allow_html=True)

    with tabs[2]:
        rk = ranking.ranks_for(s, [a.id]).get(a.id, {})
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Scale")
            st.markdown(rank_detail(rk.get("scale"), "scale"))
            st.markdown(f'<p class="note">Inputs for {a.segment.name}: ' + "; ".join(ranking.LABELS.get(m, m) for m in ranking.SCALE_INPUTS.get(a.segment_id, ranking.SCALE_INPUTS["unclassified"])) + "</p>", unsafe_allow_html=True)
        with c2:
            st.markdown("### Proximity")
            st.markdown(rank_detail(rk.get("proximity"), "proximity"))
            st.markdown('<p class="note">Input families: ' + "; ".join(ranking.PROXIMITY_FAMILIES.values()) + "</p>", unsafe_allow_html=True)
        st.markdown('<p class="note">Ranks are computed per segment from the latest snapshot, never typed in. Priority above is the team\'s decision.</p>', unsafe_allow_html=True)

    with tabs[3]:
        if a.contacts:
            st.dataframe(pd.DataFrame([{"Name": c.name, "Title": c.title or "", "Role": c.role or "", "Email": c.email or "", "Owner": c.owner or "", "Notes": c.notes or ""} for c in a.contacts]), hide_index=True, use_container_width=True)
        else:
            empty("No contacts", "Technical champion, budget owner, procurement, introduction route.")
        with st.form("contact_form", clear_on_submit=True):
            st.markdown("**Add contact**")
            c = st.columns(3)
            name = c[0].text_input("Name"); title = c[1].text_input("Title")
            role = c[2].selectbox("Role", ["", "Technical champion", "Budget owner", "Procurement", "Introduction", "Other"])
            c = st.columns(3)
            email = c[0].text_input("Email"); owner = c[1].text_input("Relationship owner"); notes = c[2].text_input("Notes")
            if st.form_submit_button("Add contact") and name.strip():
                crm.add_contact(s, a.id, name=name.strip(), title=title, role=role, email=email, owner=owner, notes=notes); st.rerun()

    with tabs[4]:
        if a.activities:
            st.dataframe(pd.DataFrame([{"Date": str(x.date), "Type": x.type, "Owner": x.owner or "", "Summary": x.summary, "Next action": x.next_action or "", "Due": str(x.due) if x.due else ""} for x in a.activities]), hide_index=True, use_container_width=True)
        else:
            empty("No activity logged", "Calls, meetings, emails and tasks appear here in order.")
        with st.form("activity_form", clear_on_submit=True):
            st.markdown("**Log activity**")
            c = st.columns([1, 2, 1])
            typ = c[0].selectbox("Type", ["Call", "Meeting", "Email", "Task", "Note"]); owner = c[1].text_input("Owner")
            due = c[2].date_input("Next action due", value=None)
            summary = st.text_area("Summary", height=70)
            nxt = st.text_input("Next action (updates the account)")
            if st.form_submit_button("Log") and summary.strip():
                crm.add_activity(s, a.id, typ, summary, owner, nxt, due); st.rerun()
