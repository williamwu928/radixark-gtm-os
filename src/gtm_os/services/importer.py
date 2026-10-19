"""Importers: the researched register (seed) and the LF AI & Data landscape.

Both follow the same shape: freeze → normalize → resolve identity → load with
provenance. Imports create research records only; they never write CRM fields
(relationship_status, owner, priority, next_action, notes, contacts, activities)
on an account that already exists.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

import yaml
from sqlalchemy import select

from gtm_os.db import (
    ROOT, Account, AccountProduct, Alias, ImportChange, ImportRun, Note, Product, Project, Segment,
    Source, session,
)

SEED_PATH = ROOT / "data/seed/radixark-crm-seed.json"
LFAI_DIR = ROOT / "data/sources/lfai"
LFAI_URL = "https://raw.githubusercontent.com/lfai/lfai-landscape/main/landscape.yml"

PRODUCT_IDS = {"SGLang": "sglang", "Miles": "miles", "SGLang-Omni": "sglang-omni"}

# LF category → proposed RadixArk segment for a NEW backing organization.
LF_CATEGORY_SEGMENT = {
    "Machine Learning": "models", "Deep Learning": "models", "Generative AI": "models",
    "Natural Language Processing": "models", "Reinforcement Learning": "data", "Model": "platform",
    "Data": "platform", "Programming": "platform", "Notebook Environment": "platform",
    "Distributed Computing": "cloud", "Trusted & Responsible AI": "platform", "Security & Privacy": "platform",
    "LF AI & Data Member Company": "enterprise", "Hosting Companies": "enterprise",
}
FOUNDATION_SLUGS = {"lf-artificial-intelligence-foundation", "apache", "linux-foundation", "the-linux-foundation",
                    "cloud-native-computing-foundation", "eclipse-foundation", "numfocus", "openjs-foundation"}

# ---------- helpers ----------
def norm_name(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"\b(inc|corp|corporation|co|ltd|llc|limited|technologies|technology|company|private|pte|gmbh|ag|sa|plc)\b\.?", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def domain_of(url: str | None) -> str | None:
    if not url:
        return None
    host = urlparse(url if "://" in url else "https://" + url).netloc.lower()
    return host[4:] if host.startswith("www.") else host or None


def github_org(url: str | None) -> str | None:
    m = re.search(r"github\.com/([A-Za-z0-9_.-]+)", url or "")
    return m.group(1).lower() if m else None


def cb_slug(url: str | None) -> str | None:
    m = re.search(r"crunchbase\.com/organization/([^/?#]+)", url or "")
    return m.group(1).lower() if m else None


class Resolver:
    """Exact alias → domain → github org → crunchbase → normalized name. Near-misses go to review."""

    def __init__(self, s):
        self.s = s
        self.by = {"domain": {}, "github_org": {}, "crunchbase": {}, "name": {}, "alias": {}}
        for a in s.execute(select(Account)).scalars():
            self._index(a)
        for al in s.execute(select(Alias)).scalars():
            self.by["alias"].setdefault(al.value.lower(), al.account_id)

    def _index(self, a: Account):
        if a.domain: self.by["domain"].setdefault(a.domain, a.id)
        if a.github_org: self.by["github_org"].setdefault(a.github_org.lower(), a.id)
        if a.crunchbase_slug: self.by["crunchbase"].setdefault(a.crunchbase_slug, a.id)
        self.by["name"].setdefault(norm_name(a.name), a.id)

    def add(self, a: Account):
        self._index(a)

    def resolve(self, *, name: str, domain=None, gh=None, cb=None, lf_name=None):
        for key, val in (("alias", (lf_name or name).lower()), ("domain", domain), ("github_org", gh), ("crunchbase", cb), ("name", norm_name(name))):
            if val and val in self.by[key]:
                return self.by[key][val], key
        # near miss: one normalized name is a prefix of the other (Alibaba / Alibaba Cloud)
        n = norm_name(name)
        for other, aid in self.by["name"].items():
            if n and other and n != other and (n.startswith(other + " ") or other.startswith(n + " ")):
                return aid, "review"
        return None, None


def _add_alias(s, account_id, alias_type, value):
    if not value: return
    exists = s.execute(select(Alias).where(Alias.account_id == account_id, Alias.alias_type == alias_type, Alias.value == value)).first()
    if not exists:
        s.add(Alias(account_id=account_id, alias_type=alias_type, value=value))


# ---------- Seed register ----------
def import_seed(path: Path = SEED_PATH) -> ImportRun:
    seed = json.loads(Path(path).read_text())
    log = []
    with session() as s:
        run = ImportRun(source="seed", snapshot_ref=str(path.name))
        s.add(run); s.flush()
        for i, seg in enumerate(seed["segments"]):
            if not s.get(Segment, seg["id"]):
                s.add(Segment(id=seg["id"], name=seg["name"], fit_hypothesis=seg.get("fit_hypothesis"), sort_order=i))
        if not s.get(Segment, "oss_foundation"):
            s.add(Segment(id="oss_foundation", name="Foundations and OSS communities", fit_hypothesis="Project hosting; ecosystem visibility", sort_order=99))
        for pname, pid in PRODUCT_IDS.items():
            if not s.get(Product, pid):
                s.add(Product(id=pid, name=pname))
        for sid, src in seed["sources"].items():
            if not s.get(Source, sid):
                s.add(Source(id=sid, title=src["title"], url=src.get("url"), type=src.get("type"), published=src.get("published") or src.get("date")))
        s.flush()
        existing = {a.id for a in s.execute(select(Account)).scalars()}
        # parent for Alibaba business unit (split 5 in seed-migration-notes)
        for a in seed["accounts"]:
            if a["account_id"] in existing:
                continue  # never overwrite an existing account
            acc = Account(id=a["account_id"], name=a["name"], business_unit=a.get("business_unit"), segment_id=a.get("segment_proposed"),
                          segment_confirmed=True, vertical=a.get("vertical_proposed"), origin="researched",
                          relationship_status="Unset", owner=a.get("owner"), priority=a.get("priority"), next_action=a.get("next_action"))
            if a["name"] == "Alibaba" and a.get("business_unit"):
                parent_id = "ACC-019P"
                if parent_id not in existing and not s.get(Account, parent_id):
                    s.add(Account(id=parent_id, name="Alibaba", segment_id="cloud", segment_confirmed=True, origin="researched", relationship_status="Unset"))
                    s.flush(); log.append("split: created Alibaba parent ACC-019P")
                acc.name = f"Alibaba Cloud / {a['business_unit']}"; acc.parent_id = parent_id
                log.append("split: ACC-019 kept as Alibaba Cloud / Bailian under ACC-019P")
            if a["name"] == "LinkedIn":
                acc.parent_id = "ACC-002"; log.append("hierarchy: LinkedIn → Microsoft corporate parent")
            s.add(acc); s.flush()
            _add_alias(s, acc.id, "display_name", a["name"])
            confirmed = "Documented product user" in a.get("relationship_tags", [])
            for p in a.get("products", []):
                s.add(AccountProduct(account_id=acc.id, product_id=PRODUCT_IDS[p], relevance="Confirmed use" if confirmed else "Suggested fit"))
            if any("investor" in e["claim"].lower() for e in seed["evidence"] if e["account_id"] == acc.id):
                log.append(f"investor mention kept as note only: {acc.name}")
            run.added += 1
            s.add(ImportChange(run_id=run.id, kind="added", entity="account", entity_id=acc.id, detail=acc.name))
        # research notes from the register's sourced facts
        have = {(n.account_id, n.text) for n in s.execute(select(Note)).scalars()}
        for e in seed["evidence"]:
            if (e["account_id"], e["claim"]) in have: continue
            src = seed["sources"].get(e["source_id"], {})
            s.add(Note(account_id=e["account_id"], text=e["claim"], source_id=e["source_id"], source_url=src.get("url"),
                       date=date.fromisoformat(e["reviewed"]), author="register"))
        # RadixArk's own projects
        for pid, name, org in (("sglang", "SGLang", "sgl-project"), ("miles", "Miles", "radixark"), ("sglang-omni", "SGLang-Omni", "sgl-project")):
            if not s.get(Project, pid):
                s.add(Project(id=pid, name=name, repo_url=f"https://github.com/{org}", role="RadixArk product", origin="researched"))
        run.log = log; s.commit(); s.refresh(run)
        return run


# ---------- LF AI & Data landscape ----------
def fetch_lfai(snapshot_date: str | None = None) -> Path:
    import urllib.request
    snapshot_date = snapshot_date or date.today().isoformat()
    LFAI_DIR.mkdir(parents=True, exist_ok=True)
    out = LFAI_DIR / f"landscape-{snapshot_date}.yml"
    if not out.exists():
        with urllib.request.urlopen(LFAI_URL, timeout=60) as r:
            out.write_bytes(r.read())
    return out


def latest_lfai_snapshot() -> Path | None:
    files = sorted(LFAI_DIR.glob("landscape-*.yml")) if LFAI_DIR.exists() else []
    return files[-1] if files else None


def normalize_lfai(path: Path) -> tuple[list[dict], list[dict]]:
    """Allowlisted fields only: name, homepage_url, repo_url, crunchbase, project. Crunchbase-derived
    enrichment is never read. Returns (organizations, projects)."""
    d = yaml.safe_load(path.read_text())
    orgs: dict[str, dict] = {}
    projects: list[dict] = []
    for cat in d["landscape"]:
        for sub in cat.get("subcategories", []):
            for it in sub.get("items", []):
                cb = cb_slug(it.get("crunchbase")); gh = github_org(it.get("repo_url"))
                cpath = f"{cat['name']} / {sub['name']}"
                is_org = cat["name"] in ("LF AI & Data Member Company", "Hosting Companies")
                if is_org:
                    key = cb or norm_name(it["name"])
                    o = orgs.setdefault(key, {"key": key, "name": it["name"], "homepage": it.get("homepage_url"), "cb": cb, "gh": None, "cats": [], "lf_names": set()})
                    o["cats"].append(cpath); o["lf_names"].add(it["name"])
                    if not o["homepage"]: o["homepage"] = it.get("homepage_url")
                else:
                    projects.append({"name": it["name"], "repo_url": it.get("repo_url"), "homepage": it.get("homepage_url"),
                                     "hosting": it.get("project"), "cb": cb, "gh": gh, "cat": cpath})
                    if cb:  # backing organization identified by its crunchbase slug (an identifier, not enrichment)
                        o = orgs.setdefault(cb, {"key": cb, "name": _slug_title(cb), "homepage": None, "cb": cb, "gh": None, "cats": [], "lf_names": set()})
                        o["cats"].append(cpath)
                        if gh and not o["gh"]: o["gh"] = gh
    return list(orgs.values()), projects


def _slug_title(slug: str) -> str:
    special = {"ibm": "IBM", "nvidia": "NVIDIA", "amd": "AMD", "sap": "SAP", "aws": "AWS", "zte-corporation": "ZTE",
               "lf-artificial-intelligence-foundation": "LF AI & Data Foundation", "apache": "Apache Software Foundation",
               "facebook": "Meta", "google": "Google", "microsoft": "Microsoft", "huawei": "Huawei", "intel": "Intel",
               "alibaba": "Alibaba", "alibaba-cloud": "Alibaba Cloud", "baidu": "Baidu", "tencent": "Tencent", "uber": "Uber",
               "hugging-face": "Hugging Face", "databricks": "Databricks", "oracle": "Oracle", "salesforce": "Salesforce"}
    return special.get(slug, slug.replace("-", " ").title())


def _propose_segment(o) -> str:
    if o["cb"] in FOUNDATION_SLUGS or "foundation" in o["name"].lower():
        return "oss_foundation"
    votes = {}
    for c in o["cats"]:
        seg = LF_CATEGORY_SEGMENT.get(c.split(" / ")[0], "platform")
        if c.startswith(("LF AI & Data Member Company", "Hosting Companies")) and len(o["cats"]) > 1:
            continue  # membership says little about what the company does; use its projects' categories
        votes[seg] = votes.get(seg, 0) + 1
    return max(votes, key=votes.get) if votes else "enterprise"


def import_lfai(path: Path | None = None) -> ImportRun:
    path = path or latest_lfai_snapshot() or fetch_lfai()
    orgs, projects = normalize_lfai(path)
    snap = re.search(r"(\d{4}-\d{2}-\d{2})", path.name).group(1)
    with session() as s:
        run = ImportRun(source="lfai", snapshot_ref=path.name); s.add(run); s.flush()
        res = Resolver(s)
        seen_accounts, seen_projects = set(), set()
        n = s.execute(select(Account).where(Account.id.like("LF-%"))).scalars().all()
        counter = len(n)
        key_to_account: dict[str, str] = {}
        for o in orgs:
            aid, how = res.resolve(name=o["name"], domain=domain_of(o["homepage"]), gh=o["gh"], cb=o["cb"], lf_name=next(iter(o["lf_names"]), None))
            if how == "review":
                run.needs_review += 1
                s.add(ImportChange(run_id=run.id, kind="review", entity="account", entity_id=aid, detail=f"LF '{o['name']}' resembles existing account {aid}; not merged"))
                aid = None
            if aid:
                a = s.get(Account, aid)
                changed = False
                for field, val in (("crunchbase_slug", o["cb"]), ("github_org", o["gh"]), ("homepage", o["homepage"]), ("domain", domain_of(o["homepage"]))):
                    if val and not getattr(a, field): setattr(a, field, val); changed = True
                if a.source_category is None: a.source_category = "; ".join(sorted(set(o["cats"])))[:200]; changed = True
                a.landscape_stale = False
                for ln in o["lf_names"]: _add_alias(s, a.id, "lf_name", ln)
                if changed: run.changed += 1; s.add(ImportChange(run_id=run.id, kind="changed", entity="account", entity_id=a.id, detail="enriched identifiers from LF"))
            else:
                counter += 1; aid = f"LF-{counter:04d}"
                a = Account(id=aid, name=o["name"], origin="lfai", segment_id=_propose_segment(o), segment_confirmed=False,
                            source_category="; ".join(sorted(set(o["cats"])))[:200], homepage=o["homepage"], domain=domain_of(o["homepage"]),
                            github_org=o["gh"], crunchbase_slug=o["cb"], relationship_status="Unset", next_action="Confirm segment; decide whether to pursue")
                s.add(a); s.flush(); res.add(a)
                _add_alias(s, aid, "display_name", o["name"])
                for ln in o["lf_names"]: _add_alias(s, aid, "lf_name", ln)
                run.added += 1; s.add(ImportChange(run_id=run.id, kind="added", entity="account", entity_id=aid, detail=o["name"]))
            key_to_account[o["key"]] = aid; seen_accounts.add(aid)
        # projects
        for p in projects:
            pid = "lf-" + re.sub(r"[^a-z0-9]+", "-", p["name"].lower()).strip("-")[:70]
            org_id = key_to_account.get(p["cb"]) if p["cb"] else None
            existing = s.get(Project, pid)
            if existing:
                existing.stale = False
                if org_id and not existing.org_account_id: existing.org_account_id = org_id
            else:
                s.add(Project(id=pid, name=p["name"], repo_url=p["repo_url"], homepage=p["homepage"], org_account_id=org_id,
                              role="LF project" if p["hosting"] else "OSS project", hosting_status=p["hosting"], source_category=p["cat"], origin="lfai"))
                s.add(ImportChange(run_id=run.id, kind="added", entity="project", entity_id=pid, detail=p["name"]))
            seen_projects.add(pid)
        # removed since last snapshot → mark stale, never delete
        for a in s.execute(select(Account).where(Account.origin == "lfai")).scalars():
            if a.id not in seen_accounts and not a.landscape_stale:
                a.landscape_stale = True; run.removed += 1
                s.add(ImportChange(run_id=run.id, kind="removed", entity="account", entity_id=a.id, detail=f"{a.name} no longer in LF landscape"))
        for p in s.execute(select(Project).where(Project.origin == "lfai")).scalars():
            if p.id not in seen_projects and not p.stale:
                p.stale = True
        run.log = [f"snapshot {snap}", f"{len(orgs)} organizations, {len(projects)} projects normalized", "fields read: name, homepage_url, repo_url, crunchbase (slug only), project"]
        s.commit(); s.refresh(run)
        return run


def bootstrap() -> list[str]:
    """Idempotent first boot: seed, then the frozen LF snapshot if present."""
    from gtm_os.db import init_db, is_empty
    init_db()
    msgs = []
    if is_empty():
        r = import_seed(); msgs.append(f"seed: {r.added} accounts")
        snap = latest_lfai_snapshot()
        if snap:
            r2 = import_lfai(snap); msgs.append(f"lfai: +{r2.added} accounts, {r2.needs_review} to review")
    return msgs
