"""Import the researched register (radixark-crm-seed.json).

Idempotent: accounts are keyed by their ACC ids, notes by evidence id. CRM fields are only set
on first creation; a re-run never overwrites relationship status, owner, priority or next action.
Hierarchy splits from docs/seed-migration-notes.md are applied here and reported in the run log.
"""
from __future__ import annotations
import json
from datetime import date
from sqlalchemy import select
from sqlalchemy.orm import Session
from .. import config
from ..models import Segment, Account, Product, AccountProduct, Source, Note, Project, ImportRun, ImportChange
from ..services.resolution import Resolver, Candidate

UNCLASSIFIED = ("unclassified", "Unclassified (assign a segment)", "Segment not yet assigned by the team")


def ensure_reference(s: Session, seed: dict):
    order = {sid: i for i, sid in enumerate(["hardware", "cloud", "models", "platform", "applications", "enterprise", "data"])}
    for seg in seed["segments"]:
        if not s.get(Segment, seg["id"]):
            s.add(Segment(id=seg["id"], name=seg["name"], fit_hypothesis=seg.get("fit_hypothesis"), sort_order=order.get(seg["id"], 50)))
    if not s.get(Segment, UNCLASSIFIED[0]):
        s.add(Segment(id=UNCLASSIFIED[0], name=UNCLASSIFIED[1], fit_hypothesis=UNCLASSIFIED[2], sort_order=99))
    for p in config.PRODUCTS:
        if not s.get(Product, p):
            s.add(Product(id=p, name=p))
    for sid, src in seed["sources"].items():
        if not s.get(Source, sid):
            s.add(Source(id=sid, title=src["title"], url=src.get("url"), type=src.get("type"), published=src.get("published") or src.get("date")))
    s.flush()


def run(s: Session, seed_file=None) -> ImportRun:
    seed_file = seed_file or config.SEED_FILE
    seed = json.load(open(seed_file))
    ensure_reference(s, seed)
    run = ImportRun(source="seed", snapshot_file=str(seed_file), snapshot_date=date.fromisoformat(seed["as_of"]))
    s.add(run); s.flush()
    log = []
    resolver = Resolver(s)

    # Parent accounts created by the migration notes
    parents = {}
    if not s.get(Account, "ACC-P01"):
        parents["Alibaba"] = Account(id="ACC-P01", name="Alibaba", segment_id="cloud", origin="Researched",
                                     next_action="Parent record: opportunities live on business units")
        s.add(parents["Alibaba"]); s.flush()
        resolver.register(parents["Alibaba"], Candidate("Alibaba", homepage="https://www.alibabagroup.com"), "seed_name")
        log.append("Created parent account Alibaba (ACC-P01)")
        run.added += 1

    for a in seed["accounts"]:
        acc = s.get(Account, a["account_id"])
        name = a["name"]
        if a["account_id"] == "ACC-019":          # Alibaba + Bailian → Alibaba Cloud / Bailian under Alibaba parent
            name = "Alibaba Cloud / Bailian"
        if acc is None:
            acc = Account(id=a["account_id"], name=name, business_unit=a.get("business_unit"),
                          segment_id=a["segment_proposed"], vertical=a.get("vertical_proposed"), origin="Researched",
                          relationship_status="Unset", owner=a.get("owner"), priority=a.get("priority") or "Unset",
                          next_action=a.get("next_action"))
            s.add(acc); s.flush()
            resolver.register(acc, Candidate(name), "seed_name")
            if name != a["name"]:
                resolver.register(acc, Candidate(a["name"]), "seed_name")
            s.add(ImportChange(run_id=run.id, kind="added", entity="account", entity_id=acc.id, source_name=a["name"]))
            run.added += 1
        else:
            run.matched += 1
        # research fields may be refreshed; CRM fields are not
        acc.segment_id = a["segment_proposed"]
        acc.vertical = a.get("vertical_proposed")
        if a["account_id"] == "ACC-019":
            acc.parent_id = "ACC-P01"
        if a["account_id"] == "ACC-006":          # LinkedIn → Microsoft corporate parent, separate operating account
            acc.parent_id = "ACC-002"
        for p in a.get("products", []):
            if not s.scalar(select(AccountProduct).where(AccountProduct.account_id == acc.id, AccountProduct.product_id == p)):
                s.add(AccountProduct(account_id=acc.id, product_id=p))

    # reviewed external keys
    import csv
    from ..models import AccountAlias
    with open(config.DATA_DIR / "seed" / "aliases.csv") as f:
        for r in csv.DictReader(f):
            acc = s.get(Account, r["account_id"])
            if acc is None or s.scalar(select(AccountAlias).where(AccountAlias.alias_type == r["alias_type"], AccountAlias.value == r["value"])):
                continue
            s.add(AccountAlias(account_id=acc.id, alias_type=r["alias_type"], value=r["value"]))
            if r["alias_type"] == "domain" and not acc.domain: acc.domain = r["value"]
            if r["alias_type"] == "github_login" and not acc.github_org: acc.github_org = r["value"]
            if r["alias_type"] == "hf_org" and not acc.hf_org: acc.hf_org = r["value"]
    s.flush()
    log.append("ACC-019 renamed to 'Alibaba Cloud / Bailian' under parent ACC-P01; ACC-006 LinkedIn linked to ACC-002 Microsoft as corporate parent")

    for e in seed["evidence"]:
        if s.scalar(select(Note).where(Note.seed_ref == e["evidence_id"])):
            continue
        src = seed["sources"].get(e["source_id"], {})
        s.add(Note(account_id=e["account_id"], text=e["claim"], source_id=e["source_id"], source_url=src.get("url"),
                   date=date.fromisoformat(e["reviewed"]), author="Research register", seed_ref=e["evidence_id"]))
    for pid, role, org in [("SGLang", "RadixArk product", "sgl-project"), ("Miles", "RadixArk product", "radixark"), ("SGLang-Omni", "RadixArk product", "sgl-project")]:
        if not s.get(Project, pid):
            s.add(Project(id=pid, name=pid, role=role, origin="Researched", github_org=org,
                          repo_url=f"https://github.com/{org}/{pid.lower()}"))
    run.log = "\n".join(log)
    s.commit()
    return run
