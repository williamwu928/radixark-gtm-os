from __future__ import annotations
from datetime import date
from pathlib import Path
import pandas as pd
import streamlit as st
from sqlalchemy import select, func
from ..models import ImportRun, ImportChange, Source, Note, Account, Metric
from ..adapters import landscape, signals
from ..services import ranking, resolution
from .. import config
from . import empty, go_account

SIGNALS = [
    ("Model downloads, releases, providers", "Scale (model developers), Proximity", "Hugging Face API", "huggingface"),
    ("Org repos, stars, contributors to sgl-project / Miles", "Proximity, Scale", "GitHub API", "github"),
    ("Co-authored statements and events", "Proximity", "Research notes", "register"),
]


def render(s):
    st.markdown("# Research")
    st.markdown('<p class="sub">Where accounts, ranks and notes come from, and what changed on each run.</p>', unsafe_allow_html=True)
    t1, t2, t3 = st.tabs(["Landscape imports", "Signals", "Sources"])

    with t1:
        runs = list(s.scalars(select(ImportRun).where(ImportRun.source.in_(["seed", "lfai", "mad"])).order_by(ImportRun.ran_at.desc())))
        st.dataframe(pd.DataFrame([{"Run": r.id, "Source": {"seed": "Researched register", "lfai": "LF AI & Data", "mad": "FirstMark MAD"}[r.source],
                                    "Snapshot": str(r.snapshot_date), "Ran": r.ran_at.strftime("%Y-%m-%d %H:%M"), "Added": r.added, "Matched": r.matched,
                                    "For review": r.needs_review, "Status": r.status} for r in runs]) if runs else pd.DataFrame(), hide_index=True, use_container_width=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Run LF AI & Data import**")
            files = sorted((config.SOURCES_DIR / "lfai").glob("*.yml"), reverse=True) if (config.SOURCES_DIR / "lfai").exists() else []
            st.markdown(f'<p class="note">Frozen snapshots on disk: {", ".join(f.name for f in files) or "none"}. A new snapshot is fetched from the LF repo.</p>', unsafe_allow_html=True)
            if st.button("Fetch new LF snapshot and import"):
                with st.spinner("Fetching landscape.yml"):
                    import requests
                    r = requests.get("https://raw.githubusercontent.com/lfai/lfai-landscape/main/landscape.yml", timeout=60)
                    r.raise_for_status()
                    d = config.SOURCES_DIR / "lfai"; d.mkdir(parents=True, exist_ok=True)
                    f = d / f"{date.today()}.yml"; f.write_bytes(r.content)
                    run = landscape.run(s, "lfai", f)
                st.success(run.log); st.rerun()
        with c2:
            st.markdown("**Run FirstMark MAD import**")
            mad_dir = config.SOURCES_DIR / "mad"
            mad_files = sorted(mad_dir.glob("*.yml"), reverse=True) if mad_dir.exists() else []
            if not mad_files:
                st.markdown('<p class="note">Not run. Reuse licence to be confirmed; then place the MAD landscape.yml at <code>data/sources/mad/YYYY-MM-DD.yml</code> or upload it here.</p>', unsafe_allow_html=True)
            up = st.file_uploader("Upload MAD landscape.yml", type=["yml", "yaml"], key="mad_up")
            if up is not None and st.button("Import uploaded MAD file"):
                mad_dir.mkdir(parents=True, exist_ok=True)
                f = mad_dir / f"{date.today()}.yml"; f.write_bytes(up.getvalue())
                run = landscape.run(s, "mad", f); st.success(run.log); st.rerun()
            if mad_files and st.button(f"Import {mad_files[0].name}"):
                run = landscape.run(s, "mad", mad_files[0]); st.success(run.log); st.rerun()

        st.markdown("## Needs review")
        reviews = list(s.scalars(select(ImportChange).where(ImportChange.kind == "review", ImportChange.resolved == False)))  # noqa: E712
        if not reviews:
            st.markdown('<p class="note">Nothing waiting. Near-miss name matches appear here for a decision.</p>', unsafe_allow_html=True)
        for ch in reviews:
            cand = s.get(Account, ch.candidate_id) if ch.candidate_id else None
            c = st.columns([4, 1, 1, 1])
            c[0].markdown(f"**{ch.source_name}** — {ch.detail}")
            if cand and c[1].button(f"Merge into {cand.name}", key=f"m{ch.id}"):
                resolution.Resolver(s).register(cand, resolution.Candidate(ch.source_name), "lfai_name")
                ch.resolved = True; s.commit(); st.rerun()
            if c[2].button("Create new account", key=f"n{ch.id}"):
                run = s.get(ImportRun, ch.run_id)
                prefix = landscape.PREFIX.get(run.source, "LF")
                acc = Account(id=landscape.next_id(s, prefix, Account), name=ch.source_name, segment_id="unclassified", origin=landscape.ORIGIN.get(run.source, "LF AI & Data"),
                              source_category=ch.detail, relationship_status="Unset", priority="Unset")
                s.add(acc); s.flush()
                resolution.Resolver(s).register(acc, resolution.Candidate(ch.source_name), f"{run.source}_name")
                ch.resolved = True; ch.entity_id = acc.id; s.commit(); st.rerun()
            if c[3].button("Ignore", key=f"i{ch.id}"):
                ch.resolved = True; s.commit(); st.rerun()

        st.markdown("## Latest changes")
        last = runs[0] if runs else None
        if last:
            chs = list(s.scalars(select(ImportChange).where(ImportChange.run_id == last.id).order_by(ImportChange.kind)))
            st.dataframe(pd.DataFrame([{"Kind": c.kind, "Entity": c.entity, "Name": c.source_name, "ID": c.entity_id or "", "Detail": c.detail or ""} for c in chs]), hide_index=True, use_container_width=True, height=400)

    with t2:
        last = {}
        for r in s.scalars(select(ImportRun).where(ImportRun.source.in_(["huggingface", "github", "register"])).order_by(ImportRun.ran_at)):
            last[r.source] = r
        cover = dict(s.execute(select(Metric.source, func.count(func.distinct(Metric.account_id))).group_by(Metric.source)).all())
        st.dataframe(pd.DataFrame([{"Signal": a, "Feeds": b, "Source": c, "Last run": (last[k].ran_at.strftime("%Y-%m-%d %H:%M") + (" · " + last[k].status if last[k].status != "ok" else "")) if k in last else "None",
                                    "Accounts covered": cover.get(k, 0), "Log": last[k].log if k in last else ""} for a, b, c, k in SIGNALS]), hide_index=True, use_container_width=True)
        c1, c2 = st.columns([1, 3])
        if c1.button("Run all snapshots and recompute ranks", type="primary"):
            with st.spinner("Running Hugging Face, GitHub and register snapshots. This takes a few minutes."):
                runs = signals.run_all(s)
            for r in runs:
                (st.success if r.status == "ok" else st.warning)(f"{r.source}: {r.log}")
        if c2.button("Recompute ranks only"):
            st.success(f"Ranked {ranking.compute(s)['ranked']} accounts")
        st.markdown(f'<p class="note">Tokens: HF_TOKEN {"set" if config.HF_TOKEN else "not set (public rate limits)"}, GITHUB_TOKEN {"set" if config.GITHUB_TOKEN else "not set (60 requests/hour; set it before running GitHub)"}.</p>', unsafe_allow_html=True)
        st.markdown(f"**Rubric {config.RUBRIC_VERSION}** — Scale inputs per segment: " + "; ".join(f"*{k}*: {', '.join(ranking.LABELS.get(m, m) for m in v)}" for k, v in ranking.SCALE_INPUTS.items() if k != 'unclassified'))

    with t3:
        srcs = list(s.scalars(select(Source).order_by(Source.id)))
        counts = dict(s.execute(select(Note.source_id, func.count()).group_by(Note.source_id)).all())
        st.dataframe(pd.DataFrame([{"ID": x.id, "Title": x.title, "URL": x.url or "", "Type": (x.type or "").replace("_", " "), "Published": x.published or "", "Notes using it": counts.get(x.id, 0)} for x in srcs]),
                     hide_index=True, use_container_width=True, column_config={"URL": st.column_config.LinkColumn()})
