"""RadixArk GTM OS — Streamlit entry point."""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import func, or_, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gtm_os.db import (Account, AccountProduct, Activity, Contact, ImportChange, ImportRun, ModelRecord, Note, Product, Project,  # noqa: E402
                       Rank, Segment, Source, session)
from gtm_os.services.importer import bootstrap, fetch_lfai, import_lfai, import_seed  # noqa: E402

st.set_page_config(page_title="RadixArk GTM OS", page_icon="▣", layout="wide", initial_sidebar_state="expanded")

STATUSES = ["Unset", "Customer", "Partner", "Open-source user", "Prospect", "None"]
PRIORITIES = ["", "P0", "P1", "P2", "P3"]
ORIGIN_LABEL = {"researched": "Researched", "lfai": "LF AI & Data", "mad": "MAD", "manual": "Manual"}

st.markdown("""<style>
:root{--accent:#D55816}
.stApp{background:#FFFFFF}
section[data-testid="stSidebar"]{background:#F6F4F1;border-right:1px solid #E6E2DD}
h1{font-size:1.45rem!important;font-weight:600!important}
h2,h3{font-weight:600!important}
.kpi{border:1px solid #E6E2DD;padding:.6rem .8rem;background:#fff}
.kpi .n{font-size:1.5rem;font-weight:600;line-height:1.1}.kpi .n.na{font-size:.95rem;color:#6B645E;font-weight:500}
.kpi .l{font-size:.78rem;color:#6B645E;margin-top:.1rem}
.pill{display:inline-block;font-size:.72rem;padding:.1rem .5rem;border-radius:999px;border:1px solid #CBC5BD;margin:0 .15rem .15rem 0}
.pill.prod{background:#FBE6DA;border-color:transparent}
.muted{color:#6B645E;font-size:.82rem}
.note{border-left:3px solid #CBC5BD;padding:.4rem .7rem;margin:.3rem 0;background:#FAFAF8}
.note .m{font-size:.72rem;color:#6B645E;font-family:ui-monospace,Menlo,monospace}
div[data-testid="stMetric"]{border:1px solid #E6E2DD;padding:.5rem .8rem}
</style>""", unsafe_allow_html=True)


# ---------- auth ----------
def gate() -> None:
    pw = os.environ.get("APP_PASSWORD")
    if not pw:
        return
    if st.session_state.get("authed"):
        return
    st.title("RadixArk GTM OS")
    with st.form("login"):
        given = st.text_input("Team password", type="password")
        if st.form_submit_button("Sign in") and given == pw:
            st.session_state.authed = True; st.rerun()
        elif given:
            st.error("That password does not match.")
    st.stop()


@st.cache_resource
def _boot():
    return bootstrap()


gate()
boot_msgs = _boot()


# ---------- helpers ----------
def seg_map() -> dict[str, str]:
    with session() as s:
        return {x.id: x.name for x in s.execute(select(Segment).order_by(Segment.sort_order)).scalars()}


def rank_map() -> dict[tuple[str, str], Rank]:
    with session() as s:
        return {(r.account_id, r.kind): r for r in s.execute(select(Rank)).scalars()}


def rank_txt(r: Rank | None) -> str:
    return f"{r.rank} / {r.of}" if r and r.rank else "Not computed"


def kpi(col, n, label, na=False):
    col.markdown(f'<div class="kpi"><div class="n {"na" if na else ""}">{n}</div><div class="l">{label}</div></div>', unsafe_allow_html=True)


def go_account(aid: str):
    st.session_state.acct = aid
    st.session_state.page = "Accounts"


def accounts_df(filters: dict) -> pd.DataFrame:
    segs = seg_map(); ranks = rank_map()
    with session() as s:
        q = select(Account)
        if filters.get("q"):
            like = f"%{filters['q']}%"
            q = q.where(or_(Account.name.ilike(like), Account.vertical.ilike(like), Account.source_category.ilike(like)))
        if filters.get("segment"): q = q.where(Account.segment_id == filters["segment"])
        if filters.get("origin"): q = q.where(Account.origin == filters["origin"])
        if filters.get("status"): q = q.where(Account.relationship_status == filters["status"])
        if filters.get("owner") == "Unassigned": q = q.where(Account.owner.is_(None))
        elif filters.get("owner"): q = q.where(Account.owner == filters["owner"])
        if filters.get("unconfirmed"): q = q.where(Account.segment_confirmed.is_(False))
        if not filters.get("stale"): q = q.where(Account.landscape_stale.is_(False))
        accs = s.execute(q.order_by(Account.origin.desc(), Account.name)).scalars().all()
        prods = {}
        for ap in s.execute(select(AccountProduct)).scalars(): prods.setdefault(ap.account_id, []).append(ap.product.name)
        if filters.get("product"):
            accs = [a for a in accs if filters["product"] in prods.get(a.id, [])]
        rows = []
        for a in accs:
            sc, px = ranks.get((a.id, "scale")), ranks.get((a.id, "proximity"))
            rows.append({"id": a.id, "Account": a.name, "Origin": ORIGIN_LABEL.get(a.origin, a.origin), "Segment": segs.get(a.segment_id, "—") + ("" if a.segment_confirmed else " (proposed)"),
                         "Vertical": a.vertical or "—", "Products": ", ".join(prods.get(a.id, [])) or "—", "Relationship status": a.relationship_status,
                         "Scale rank": rank_txt(sc), "Proximity rank": rank_txt(px), "Scale score": sc.score if sc else None,
                         "Owner": a.owner or "Unassigned", "Priority": a.priority or "—", "Next action": a.next_action or "—"})
    df = pd.DataFrame(rows)
    if len(df) and filters.get("sort") == "Scale rank":
        df = df.sort_values(["Scale score"], ascending=False, na_position="last")
    return df


# ---------- views ----------
def view_overview():
    st.title("Overview")
    st.markdown('<p class="muted">Counts describe the account register, not the market. Landscape-sourced accounts are counted separately from researched ones.</p>', unsafe_allow_html=True)
    segs = seg_map()
    with session() as s:
        total = s.scalar(select(func.count(Account.id)).where(Account.landscape_stale.is_(False)))
        researched = s.scalar(select(func.count(Account.id)).where(Account.origin == "researched"))
        lf = s.scalar(select(func.count(Account.id)).where(Account.origin == "lfai", Account.landscape_stale.is_(False)))
        status_set = s.scalar(select(func.count(Account.id)).where(Account.relationship_status != "Unset"))
        owned = s.scalar(select(func.count(Account.id)).where(Account.owner.isnot(None)))
        ranked = s.scalar(select(func.count(func.distinct(Rank.account_id))))
        due = s.scalar(select(func.count(Account.id)).where(Account.next_action_due.isnot(None), Account.next_action_due <= date.today()))
        seg_counts = dict(s.execute(select(Account.segment_id, func.count()).where(Account.landscape_stale.is_(False)).group_by(Account.segment_id)).all())
        seg_origin = {(sg, o): n for sg, o, n in s.execute(select(Account.segment_id, Account.origin, func.count()).where(Account.landscape_stale.is_(False)).group_by(Account.segment_id, Account.origin)).all()}
        seg_status = {(sg, o): n for sg, o, n in s.execute(select(Account.segment_id, Account.relationship_status, func.count()).group_by(Account.segment_id, Account.relationship_status)).all()}
        next_rows = s.execute(select(Account).where(Account.next_action.isnot(None), Account.origin == "researched").order_by(Account.next_action_due.nulls_last(), Account.name).limit(10)).scalars().all()
        prod_counts = dict(s.execute(select(Product.name, func.count()).join(AccountProduct, AccountProduct.product_id == Product.id).group_by(Product.name)).all())
    c = st.columns(6)
    kpi(c[0], total, "Accounts"); kpi(c[1], researched, "Researched"); kpi(c[2], lf, "From LF AI & Data landscape")
    kpi(c[3], status_set, "Relationship status set"); kpi(c[4], ranked if ranked else "Not computed", "Ranked · rubric v1", na=not ranked); kpi(c[5], due, "Next actions due")

    st.subheader("Value chain · register coverage")
    cols = st.columns(len(segs))
    for col, (sid, name) in zip(cols, segs.items()):
        if col.button(f"**{seg_counts.get(sid, 0)}**\n\n{name}", key=f"seg-{sid}", width="stretch"):
            st.session_state.filters = {"segment": sid}; st.session_state.page = "Accounts"; st.rerun()
    st.markdown(" ".join(f'<span class="pill prod">{k} · {v} accounts</span>' for k, v in prod_counts.items()) + '<span class="muted"> &nbsp;Cross-cutting products. Select a segment to filter Accounts.</span>', unsafe_allow_html=True)

    st.subheader("Segment × origin and relationship status")
    rows = []
    for sid, name in segs.items():
        r = {"Segment": name, "Researched": seg_origin.get((sid, "researched"), 0), "LF AI & Data": seg_origin.get((sid, "lfai"), 0)}
        for stt in STATUSES[1:]: r[stt] = seg_status.get((sid, stt), 0)
        rows.append(r)
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    st.subheader("Scale × Proximity per segment · rubric v1")
    ranks = rank_map()
    if not ranks:
        st.info("Ranks are not computed yet. Run the Hugging Face and GitHub snapshots in Research → Signals, then compute ranks.")
    else:
        quad = []
        with session() as s:
            for a in s.execute(select(Account)).scalars():
                sc, px = ranks.get((a.id, "scale")), ranks.get((a.id, "proximity"))
                if sc or px:
                    hi_s = bool(sc and sc.rank and sc.of and sc.rank <= max(1, sc.of // 2)); hi_p = bool(px and px.score and px.score >= 2)
                    quad.append({"Segment": segs.get(a.segment_id), "Quadrant": ("High scale" if hi_s else "Low scale") + " · " + ("high proximity" if hi_p else "low proximity")})
        if quad:
            st.dataframe(pd.DataFrame(quad).value_counts().reset_index(name="Accounts").pivot(index="Segment", columns="Quadrant", values="Accounts").fillna(0).astype(int), width="stretch")

    st.subheader("Next actions")
    for a in next_rows:
        c1, c2, c3 = st.columns([3, 6, 2])
        if c1.button(a.name, key=f"na-{a.id}"): go_account(a.id); st.rerun()
        c2.write(a.next_action); c3.write(f"{a.owner or 'Unassigned'} · {a.next_action_due or 'no date'}")


def view_accounts():
    if st.session_state.get("acct"):
        return view_account_detail(st.session_state.acct)
    st.title("Accounts")
    segs = seg_map(); f = st.session_state.get("filters", {})
    with session() as s:
        owners = sorted({o for (o,) in s.execute(select(Account.owner).where(Account.owner.isnot(None))).all()})
    r1 = st.columns([3, 2, 2, 2, 2])
    f["q"] = r1[0].text_input("Search", value=f.get("q", ""), placeholder="Name, vertical or source category")
    f["segment"] = r1[1].selectbox("Segment", [""] + list(segs), index=([""] + list(segs)).index(f.get("segment", "")) if f.get("segment") in segs else 0, format_func=lambda x: segs.get(x, "All segments"))
    f["origin"] = r1[2].selectbox("Origin", ["", "researched", "lfai", "manual"], format_func=lambda x: ORIGIN_LABEL.get(x, "Any origin"))
    f["status"] = r1[3].selectbox("Relationship status", [""] + STATUSES, format_func=lambda x: x or "Any status")
    f["owner"] = r1[4].selectbox("Owner", ["", "Unassigned"] + owners, format_func=lambda x: x or "Any owner")
    r2 = st.columns([2, 2, 2, 2, 3])
    f["product"] = r2[0].selectbox("Product", ["", "SGLang", "Miles", "SGLang-Omni"], format_func=lambda x: x or "Any product")
    f["sort"] = r2[1].selectbox("Sort", ["Name", "Scale rank"])
    f["unconfirmed"] = r2[2].checkbox("Only proposed segments", value=bool(f.get("unconfirmed")))
    f["stale"] = r2[3].checkbox("Include stale landscape accounts")
    with r2[4].popover("New account"):
        with st.form("new-acct"):
            n = st.text_input("Name"); sg = st.selectbox("Segment", list(segs), format_func=segs.get); hp = st.text_input("Homepage")
            if st.form_submit_button("Create") and n.strip():
                with session() as s:
                    nid = "MAN-" + str(s.scalar(select(func.count(Account.id)).where(Account.id.like("MAN-%"))) + 1).zfill(4)
                    s.add(Account(id=nid, name=n.strip(), segment_id=sg, segment_confirmed=True, origin="manual", homepage=hp or None)); s.commit()
                go_account(nid); st.rerun()
    st.session_state.filters = f
    df = accounts_df(f)
    st.caption(f"{len(df)} accounts")
    if len(df) == 0:
        st.info("No accounts match these filters."); return
    show = df.drop(columns=["id", "Scale score"])
    ev = st.dataframe(show, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row", height=min(38 + 35 * len(show), 700))
    sel = ev.selection.rows if ev and ev.selection else []
    if sel:
        go_account(df.iloc[sel[0]]["id"]); st.rerun()


def view_account_detail(aid: str):
    segs = seg_map(); ranks = rank_map()
    with session() as s:
        a = s.get(Account, aid)
        if not a:
            st.session_state.acct = None; st.rerun()
        if st.button("← Accounts"):
            st.session_state.acct = None; st.rerun()
        st.title(a.name)
        parent = s.get(Account, a.parent_id) if a.parent_id else None
        children = s.execute(select(Account).where(Account.parent_id == a.id)).scalars().all()
        prods = [ap for ap in a.products]
        st.markdown(" ".join([f'<span class="pill">{segs.get(a.segment_id, "—")}{"" if a.segment_confirmed else " · proposed"}</span>', f'<span class="pill">{ORIGIN_LABEL.get(a.origin)}</span>',
                              f'<span class="pill">Status: {a.relationship_status}</span>', f'<span class="pill">Owner: {a.owner or "unassigned"}</span>'] +
                             [f'<span class="pill prod">{p.product.name} · {p.relevance}</span>' for p in prods] +
                             ([f'<span class="pill">Stale in landscape</span>'] if a.landscape_stale else [])), unsafe_allow_html=True)
        tabs = st.tabs(["Overview", "Models & Stack", "Ranking", "People", "Activity"])

        with tabs[0]:
            left, right = st.columns([3, 2])
            with left:
                if parent: st.write(f"Parent: **{parent.name}**")
                if children: st.write("Business units: " + ", ".join(c.name for c in children))
                if a.source_category: st.markdown(f'<p class="muted">Source category: {a.source_category}</p>', unsafe_allow_html=True)
                if a.homepage: st.write(a.homepage)
                st.subheader("Research notes")
                for n in a.notes:
                    src = f'<a href="{n.source_url}" target="_blank">{n.source.title if n.source else "source"}</a>' if n.source_url else (n.source.title if n.source else "")
                    st.markdown(f'<div class="note">{n.text}<div class="m">{src} · {n.date} · {n.author or ""}</div></div>', unsafe_allow_html=True)
                if not a.notes: st.caption("No research notes yet.")
                with st.form("add-note", clear_on_submit=True):
                    t = st.text_area("Add a research note", height=70); u = st.text_input("Source link (optional)")
                    if st.form_submit_button("Add note") and t.strip():
                        s.add(Note(account_id=a.id, text=t.strip(), source_url=u or None, author="team")); s.commit(); st.rerun()
            with right:
                st.subheader("Account")
                with st.form("edit-acct"):
                    status = st.selectbox("Relationship status", STATUSES, index=STATUSES.index(a.relationship_status) if a.relationship_status in STATUSES else 0)
                    owner = st.text_input("Owner", value=a.owner or "")
                    prio = st.selectbox("Priority", PRIORITIES, index=PRIORITIES.index(a.priority) if a.priority in PRIORITIES else 0)
                    seg = st.selectbox("Segment", list(segs), index=list(segs).index(a.segment_id) if a.segment_id in segs else 0, format_func=segs.get)
                    vert = st.text_input("Vertical", value=a.vertical or "")
                    na = st.text_area("Next action", value=a.next_action or "", height=70)
                    due = st.date_input("Due", value=a.next_action_due, format="YYYY-MM-DD")
                    prod_sel = st.multiselect("Products", ["SGLang", "Miles", "SGLang-Omni"], default=[p.product.name for p in prods])
                    if st.form_submit_button("Save"):
                        if status != a.relationship_status: a.status_date = date.today()
                        a.relationship_status = status; a.owner = owner or None; a.priority = prio or None
                        a.segment_id = seg; a.segment_confirmed = True; a.vertical = vert or None; a.next_action = na or None; a.next_action_due = due
                        keep = {p.product.name: p for p in prods}
                        for p in prods:
                            if p.product.name not in prod_sel: s.delete(p)
                        pid = {"SGLang": "sglang", "Miles": "miles", "SGLang-Omni": "sglang-omni"}
                        for pn in prod_sel:
                            if pn not in keep: s.add(AccountProduct(account_id=a.id, product_id=pid[pn], relevance="Confirmed use"))
                        s.commit(); st.success("Saved"); st.rerun()
                if a.status_date: st.caption(f"Status set {a.status_date}")

        with tabs[1]:
            with st.form("ids"):
                c1, c2, c3 = st.columns(3)
                hf = c1.text_input("Hugging Face org", value=a.hf_org or ""); gh = c2.text_input("GitHub org", value=a.github_org or ""); hp = c3.text_input("Homepage", value=a.homepage or "")
                if st.form_submit_button("Save identifiers"):
                    a.hf_org = hf or None; a.github_org = gh or None; a.homepage = hp or None; s.commit(); st.rerun()
            ms = s.execute(select(ModelRecord).where(ModelRecord.publisher_account_id == a.id).order_by(ModelRecord.downloads_30d.desc().nulls_last())).scalars().all()
            st.subheader("Models published")
            if ms:
                st.dataframe(pd.DataFrame([{"Model": m.id, "Modality": m.modality, "30-day downloads": m.downloads_30d, "Likes": m.likes, "Providers": ", ".join(m.providers or []), "Snapshot": m.snapshot_date} for m in ms]), hide_index=True, width="stretch")
            else:
                st.caption("No models on file. Set the Hugging Face org above and run the HF snapshot from Research → Signals.")
            st.subheader("Projects")
            if a.projects:
                st.dataframe(pd.DataFrame([{"Project": p.name, "Role": p.role, "Hosting": p.hosting_status or "—", "Repo": p.repo_url, "Category": p.source_category} for p in a.projects]), hide_index=True, width="stretch")
            else:
                st.caption("No projects linked.")

        with tabs[2]:
            sc, px = ranks.get((a.id, "scale")), ranks.get((a.id, "proximity"))
            c1, c2 = st.columns(2)
            with c1:
                st.metric("Scale rank · within " + segs.get(a.segment_id, ""), rank_txt(sc))
                if sc: st.json({"inputs": sc.inputs, "missing": sc.missing, "snapshot": sc.snapshot_date, "rubric": sc.rubric})
                else: st.caption("No scale inputs yet for this account.")
            with c2:
                st.metric("Proximity rank", rank_txt(px))
                if px: st.json({"inputs": px.inputs, "missing": px.missing, "snapshot": px.snapshot_date, "rubric": px.rubric})
                else: st.caption("No proximity inputs yet (contributors, SGLang-supported models, serving, co-authored posts).")
            st.caption("Ranks are recomputed from snapshots and never edited by hand. Priority is set on the Overview tab.")

        with tabs[3]:
            if a.contacts:
                st.dataframe(pd.DataFrame([{"Name": c.name, "Title": c.title, "Buying role": c.buying_role, "Email": c.email, "Owner": c.relationship_owner, "Verified": c.last_verified} for c in a.contacts]), hide_index=True, width="stretch")
            else:
                st.caption("No contacts yet.")
            with st.form("add-contact", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                n = c1.text_input("Name"); t = c2.text_input("Title"); r = c3.selectbox("Buying role", ["Technical champion", "Budget owner", "Procurement", "Introduction route", "Other"])
                e = c1.text_input("Email"); o = c2.text_input("Relationship owner")
                if st.form_submit_button("Add contact") and n.strip():
                    s.add(Contact(account_id=a.id, name=n.strip(), title=t or None, buying_role=r, email=e or None, relationship_owner=o or None, last_verified=date.today())); s.commit(); st.rerun()

        with tabs[4]:
            for act in a.activities:
                st.markdown(f'<div class="note"><b>{act.type}</b> · {act.date} · {act.owner or ""}<br>{act.summary}' + (f'<br><span class="muted">Next: {act.next_action} {act.due or ""}</span>' if act.next_action else "") + "</div>", unsafe_allow_html=True)
            if not a.activities: st.caption("No activity logged.")
            with st.form("add-act", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                ty = c1.selectbox("Type", ["Call", "Meeting", "Email", "Task", "Note"]); d = c2.date_input("Date", value=date.today(), format="YYYY-MM-DD"); o = c3.text_input("Owner", value=a.owner or "")
                sm = st.text_area("Summary", height=70); nxt = c1.text_input("Next action"); du = c2.date_input("Due", value=None, format="YYYY-MM-DD")
                if st.form_submit_button("Log activity") and sm.strip():
                    s.add(Activity(account_id=a.id, type=ty, date=d, owner=o or None, summary=sm.strip(), next_action=nxt or None, due=du))
                    if nxt: a.next_action = nxt; a.next_action_due = du
                    s.commit(); st.rerun()


def view_models():
    st.title("Models & Projects")
    t1, t2, t3 = st.tabs(["Models", "Projects", "Serving providers"])
    with session() as s:
        ms = s.execute(select(ModelRecord).order_by(ModelRecord.downloads_30d.desc().nulls_last())).scalars().all()
        ps = s.execute(select(Project).where(Project.stale.is_(False)).order_by(Project.role, Project.name)).scalars().all()
        names = {a.id: a.name for a in s.execute(select(Account)).scalars()}
    with t1:
        if ms:
            st.dataframe(pd.DataFrame([{"Model": m.id, "Publisher": names.get(m.publisher_account_id, "—"), "Modality": m.modality, "30-day downloads": m.downloads_30d, "Likes": m.likes, "Providers": ", ".join(m.providers or []), "SGLang supported": m.sglang_supported, "Snapshot": m.snapshot_date} for m in ms]), hide_index=True, width="stretch")
        else:
            st.info("No models yet. Set Hugging Face org identifiers on accounts, then run the HF snapshot in Research → Signals.")
    with t2:
        q = st.text_input("Filter projects")
        rows = [{"Project": p.name, "Role": p.role, "Hosting": p.hosting_status or "—", "Backing organization": names.get(p.org_account_id, "—"), "Category": p.source_category or "—", "Repo": p.repo_url or ""} for p in ps if not q or q.lower() in p.name.lower() or q.lower() in (names.get(p.org_account_id, "") or "").lower()]
        st.caption(f"{len(rows)} projects"); st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=600)
    with t3:
        prov = {}
        for m in ms:
            for p in (m.providers or []): prov.setdefault(p, []).append(m.id)
        if prov:
            st.dataframe(pd.DataFrame([{"Provider": k, "Models served (of those on file)": len(v)} for k, v in sorted(prov.items(), key=lambda x: -len(x[1]))]), hide_index=True, width="stretch")
        else:
            st.info("Provider mappings arrive with the Hugging Face snapshot.")


def view_research():
    st.title("Research")
    t1, t2, t3, t4 = st.tabs(["Landscape imports", "Signals", "Review queue", "Sources"])
    with t1:
        c1, c2, c3 = st.columns(3)
        if c1.button("Re-run LF AI & Data import (frozen snapshot)"):
            r = import_lfai(); st.success(f"Run {r.id}: +{r.added} added, {r.changed} changed, {r.removed} removed, {r.needs_review} to review")
        if c2.button("Fetch new LF snapshot and import"):
            try:
                p = fetch_lfai(); r = import_lfai(p); st.success(f"Snapshot {p.name}: +{r.added} added, {r.changed} changed, {r.removed} removed")
            except Exception as e:  # noqa: BLE001
                st.error(f"Fetch failed: {e}")
        if c3.button("Re-run seed register (adds missing only)"):
            r = import_seed(); st.success(f"Seed: {r.added} added")
        st.markdown('<p class="muted">FirstMark MAD: no public data file; the interactive map is PDF-only and its card data is CB Insights-licensed. MAD contributes category structure to the segment taxonomy only. LF AI & Data: landscape.yml (Apache-2.0), fields read: name, homepage_url, repo_url, crunchbase slug, project. Imports never change relationship status, owner, priority, notes, contacts or activities.</p>', unsafe_allow_html=True)
        with session() as s:
            runs = s.execute(select(ImportRun).order_by(ImportRun.ran_at.desc()).limit(30)).scalars().all()
        st.dataframe(pd.DataFrame([{"Run": r.id, "Source": r.source, "Snapshot": r.snapshot_ref, "Ran": r.ran_at.strftime("%Y-%m-%d %H:%M"), "Added": r.added, "Changed": r.changed, "Removed": r.removed, "Review": r.needs_review, "Status": r.status, "Log": " | ".join(r.log or [])} for r in runs]), hide_index=True, width="stretch")
    with t2:
        from gtm_os.adapters.signals import snapshot_github, snapshot_huggingface
        from gtm_os.services.ranking import compute_ranks
        c1, c2, c3 = st.columns(3)
        if c1.button("Run Hugging Face snapshot"):
            with st.spinner("Querying Hugging Face…"):
                r = snapshot_huggingface(); (st.success if r.status == "ok" else st.warning)(f"{r.status}: {r.added} models · " + " | ".join(r.log or []))
        if c2.button("Run GitHub snapshot"):
            with st.spinner("Querying GitHub…"):
                r = snapshot_github(); (st.success if r.status == "ok" else st.warning)(f"{r.status}: {r.added} rows · " + " | ".join(r.log or []))
        if c3.button("Compute ranks (rubric v1)"):
            st.success(str(compute_ranks()))
        with session() as s:
            hf_n = s.scalar(select(func.count(Account.id)).where(Account.hf_org.isnot(None))); gh_n = s.scalar(select(func.count(Account.id)).where(Account.github_org.isnot(None)))
            last = {r.source: r for r in s.execute(select(ImportRun).order_by(ImportRun.ran_at)).scalars()}
        st.dataframe(pd.DataFrame([
            {"Signal": "Model downloads, releases, providers", "Feeds": "Scale (model developers), Proximity", "Source": "Hugging Face API", "Accounts with identifier": str(hf_n), "Last run": last["huggingface"].ran_at.strftime("%Y-%m-%d") if "huggingface" in last else "None"},
            {"Signal": "Contributors to sgl-project / Miles; org repos", "Feeds": "Proximity, Scale", "Source": "GitHub API", "Accounts with identifier": str(gh_n), "Last run": last["github"].ran_at.strftime("%Y-%m-%d") if "github" in last else "None"},
            {"Signal": "Endpoints, pricing, throughput", "Feeds": "Scale (clouds, providers)", "Source": "Artificial Analysis", "Accounts with identifier": "—", "Last run": "Not built"},
            {"Signal": "SGLang supported models, time-to-support", "Feeds": "Proximity", "Source": "sglang.io/models", "Accounts with identifier": "—", "Last run": "Not built"},
            {"Signal": "Open ML / infra roles", "Feeds": "Scale (applications, enterprise)", "Source": "Job boards", "Accounts with identifier": "—", "Last run": "Not built"},
        ]), hide_index=True, width="stretch")
        st.caption("Set HF_TOKEN and GITHUB_TOKEN in the environment for higher rate limits.")
    with t3:
        with session() as s:
            items = s.execute(select(ImportChange).where(ImportChange.kind == "review", ImportChange.resolved.is_(False)).order_by(ImportChange.id)).scalars().all()
            if not items: st.success("Nothing to review.")
            for it in items:
                c1, c2 = st.columns([6, 1])
                c1.write(f"#{it.id} · {it.detail}")
                if c2.button("Resolve", key=f"res-{it.id}"):
                    it.resolved = True; s.commit(); st.rerun()
            st.markdown('<p class="muted">Near-miss name matches are listed here instead of being merged automatically. Merge by editing the two accounts; then resolve.</p>', unsafe_allow_html=True)
    with t4:
        with session() as s:
            srcs = s.execute(select(Source)).scalars().all()
            counts = dict(s.execute(select(Note.source_id, func.count()).group_by(Note.source_id)).all())
        st.dataframe(pd.DataFrame([{"ID": x.id, "Title": x.title, "URL": x.url or "", "Type": (x.type or "").replace("_", " "), "Published": x.published or "", "Notes using it": counts.get(x.id, 0)} for x in srcs]), hide_index=True, width="stretch")


# ---------- shell ----------
PAGES = {"Overview": view_overview, "Accounts": view_accounts, "Models & Projects": view_models, "Research": view_research}
with st.sidebar:
    st.markdown("### Radix<span style='color:#D55816'>Ark</span> GTM OS", unsafe_allow_html=True)
    page = st.radio("Views", list(PAGES), index=list(PAGES).index(st.session_state.get("page", "Overview")), label_visibility="collapsed")
    if page != st.session_state.get("page"):
        st.session_state.page = page
        if page != "Accounts": st.session_state.acct = None
    q = st.text_input("Search", placeholder="Accounts, projects, notes")
    if q:
        with session() as s:
            like = f"%{q}%"
            for a in s.execute(select(Account).where(Account.name.ilike(like)).limit(8)).scalars():
                if st.button(f"Account · {a.name}", key=f"s-a-{a.id}"): go_account(a.id); st.rerun()
            for p in s.execute(select(Project).where(Project.name.ilike(like)).limit(5)).scalars():
                st.caption(f"Project · {p.name}" + (f" ({p.org.name})" if p.org else ""))
            for n in s.execute(select(Note).where(Note.text.ilike(like)).limit(5)).scalars():
                if st.button(f"Note · {n.text[:60]}…", key=f"s-n-{n.id}"): go_account(n.account_id); st.rerun()
    st.caption("Register as of 2026-10-18 · " + " · ".join(boot_msgs) if boot_msgs else "")

PAGES[st.session_state.get("page", "Overview")]()
