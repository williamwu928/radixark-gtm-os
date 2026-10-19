"""Import a landscape2-format landscape.yml (LF AI & Data, FirstMark MAD).

Four passes: the frozen file is read (never the live site); each item becomes a candidate;
candidates are resolved against existing accounts; new accounts/projects are created with
origin and source category. Landscape membership never sets relationship status, owner or
priority. Field allowlist: name, homepage_url, repo_url, crunchbase (as an opaque id),
project hosting level. Enrichment fields (funding, headcount, Crunchbase-derived data) are not read.
"""
from __future__ import annotations
import csv
import re
from datetime import date
from pathlib import Path
import yaml
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .. import config
from ..models import Account, Project, ImportRun, ImportChange, Segment
from ..services.resolution import Resolver, Candidate, github_org_of

ORIGIN = {"lfai": "LF AI & Data", "mad": "MAD"}
PREFIX = {"lfai": "LF", "mad": "MAD"}


def load_taxonomy(source: str):
    rows = []
    with open(config.DATA_DIR / "seed" / "taxonomy.csv") as f:
        for r in csv.DictReader(f):
            if r["source"] == source:
                rows.append(r)
    return rows


def classify(rows, category: str):
    """Longest matching category prefix wins; an empty prefix is the fallback."""
    best = None
    for r in rows:
        p = r["category_prefix"]
        if category.startswith(p) and (best is None or len(p) > len(best["category_prefix"])):
            best = r
    return (best["segment"] or "unclassified", best["treat_as"]) if best else ("unclassified", "account")


def iter_items(doc: dict):
    for cat in doc.get("landscape", []):
        for sub in cat.get("subcategories", []):
            for it in sub.get("items", []):
                yield f"{cat['name']} > {sub['name']}", it


def next_id(s: Session, prefix: str, table) -> str:
    n = s.scalar(select(func.count()).select_from(table).where(table.id.like(f"{prefix}-%"))) or 0
    return f"{prefix}-{n + 1:04d}"


def run(s: Session, source: str, snapshot_file: Path, snapshot_date: date | None = None) -> ImportRun:
    doc = yaml.safe_load(open(snapshot_file))
    snapshot_date = snapshot_date or date.fromisoformat(re.sub(r"\.ya?ml$", "", snapshot_file.name))
    run = ImportRun(source=source, snapshot_file=str(snapshot_file), snapshot_date=snapshot_date)
    s.add(run); s.flush()
    tax = load_taxonomy(source)
    resolver = Resolver(s)
    name_tag = f"{source}_name"
    seen_accounts, seen_projects = set(), set()

    for category, it in iter_items(doc):
        name = it["name"]
        segment, treat = classify(tax, category)
        cand = Candidate(name, homepage=it.get("homepage_url"), repo_url=it.get("repo_url"), crunchbase=it.get("crunchbase"))
        if treat == "project":
            pid_existing = s.scalar(select(Project).where(Project.origin == ORIGIN[source], Project.name == name))
            if pid_existing:
                pid_existing.category = category; pid_existing.homepage = cand.homepage; pid_existing.repo_url = cand.repo_url
                seen_projects.add(pid_existing.id); run.matched += 1
                continue
            pr = Project(id=next_id(s, PREFIX[source] + "P", Project), name=name, role="LF project" if source == "lfai" else "Ecosystem project",
                         origin=ORIGIN[source], category=category, homepage=cand.homepage, repo_url=cand.repo_url,
                         github_org=github_org_of(cand.repo_url), hosting=it.get("project"))
            # link to a backing account only on an exact alias/domain/github match, never by name guess
            res = resolver.resolve(cand)
            if res.kind == "matched" and res.how != "name":
                pr.account_id = res.account.id
            s.add(pr); s.flush()
            seen_projects.add(pr.id)
            s.add(ImportChange(run_id=run.id, kind="added", entity="project", entity_id=pr.id, source_name=name, detail=category))
            run.added += 1
            continue

        res = resolver.resolve(cand)
        if res.kind == "matched":
            acc = res.account
            resolver.register(acc, cand, name_tag)
            if not acc.source_category:
                acc.source_category = f"{ORIGIN[source]}: {category}"
            seen_accounts.add(acc.id); run.matched += 1
            s.add(ImportChange(run_id=run.id, kind="matched", entity="account", entity_id=acc.id, source_name=name, detail=f"{res.how}; {category}", resolved=True))
        elif res.kind == "review":
            run.needs_review += 1
            s.add(ImportChange(run_id=run.id, kind="review", entity="account", source_name=name, candidate_id=res.account.id,
                               detail=f"possible match with {res.account.name} ({res.how}); {category}; homepage {cand.homepage or '—'}"))
        else:
            acc = Account(id=next_id(s, PREFIX[source], Account), name=name, segment_id=segment, origin=ORIGIN[source],
                          homepage=cand.homepage, domain=cand.domain, github_org=cand.github_org,
                          source_category=f"{ORIGIN[source]}: {category}", relationship_status="Unset", priority="Unset")
            s.add(acc); s.flush()
            resolver.register(acc, cand, name_tag)
            seen_accounts.add(acc.id); run.added += 1
            s.add(ImportChange(run_id=run.id, kind="added", entity="account", entity_id=acc.id, source_name=name, detail=category))

    # removed since the previous run of this source: accounts of this origin no longer in the file
    for acc in s.scalars(select(Account).where(Account.origin == ORIGIN[source])):
        if acc.id not in seen_accounts:
            s.add(ImportChange(run_id=run.id, kind="removed", entity="account", entity_id=acc.id, source_name=acc.name, detail="not in this snapshot; account kept"))
    run.log = f"{run.added} added, {run.matched} matched, {run.needs_review} for review"
    s.commit()
    return run
