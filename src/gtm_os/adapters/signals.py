"""Signal adapters that feed the Scale and Proximity ranks (rubric v1).

Each adapter pulls public data for accounts that carry the matching identifier,
writes a raw snapshot to data/sources/<source>/<date>.jsonl, and returns the
normalized rows. Network failures are reported, not hidden.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from sqlalchemy import select

from gtm_os.db import ROOT, Account, ImportRun, ModelRecord, session

RADIXARK_REPOS = ["sgl-project/sglang", "radixark/miles"]


def _get(url: str, headers: dict | None = None, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "radixark-gtm-os/0.1", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _write_snapshot(source: str, rows: list[dict]) -> Path:
    d = ROOT / "data/sources" / source; d.mkdir(parents=True, exist_ok=True)
    p = d / f"{date.today().isoformat()}.jsonl"
    with p.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return p


# ---------- Hugging Face ----------
def snapshot_huggingface(limit_per_org: int = 50) -> ImportRun:
    """For every account with hf_org: list models with downloads, likes, created date and inference-provider mapping."""
    today = date.today().isoformat()
    headers = {"Authorization": f"Bearer {os.environ['HF_TOKEN']}"} if os.environ.get("HF_TOKEN") else {}
    rows, errors = [], []
    with session() as s:
        run = ImportRun(source="huggingface", snapshot_ref=today); s.add(run); s.flush()
        accounts = s.execute(select(Account).where(Account.hf_org.isnot(None))).scalars().all()
        for a in accounts:
            q = urllib.parse.urlencode({"author": a.hf_org, "sort": "downloads", "direction": -1, "limit": limit_per_org,
                                        "expand[]": ["downloads", "likes", "createdAt", "pipeline_tag", "inferenceProviderMapping"]}, doseq=True)
            try:
                models = _get(f"https://huggingface.co/api/models?{q}", headers)
            except (urllib.error.URLError, OSError) as e:
                errors.append(f"{a.hf_org}: {e}"); continue
            for m in models:
                mapping = m.get("inferenceProviderMapping") or {}
                providers = list(mapping.keys()) if isinstance(mapping, dict) else [x.get("provider") for x in mapping if isinstance(x, dict)]
                row = {"account_id": a.id, "model_id": m.get("id") or m.get("modelId"), "downloads": m.get("downloads"), "likes": m.get("likes"),
                       "created_at": m.get("createdAt"), "pipeline_tag": m.get("pipeline_tag"), "providers": providers}
                rows.append(row)
                rec = s.get(ModelRecord, row["model_id"]) or ModelRecord(id=row["model_id"])
                rec.publisher_account_id = a.id; rec.downloads_30d = row["downloads"]; rec.likes = row["likes"]
                rec.created_at = row["created_at"]; rec.modality = row["pipeline_tag"]; rec.providers = providers; rec.snapshot_date = today
                s.add(rec)
            time.sleep(0.2)
        run.added = len(rows); run.status = "ok" if not errors else ("partial" if rows else "failed")
        run.log = [f"{len(accounts)} accounts with an hf_org"] + errors[:20]
        if rows: run.snapshot_ref = str(_write_snapshot("huggingface", rows).name)
        s.commit(); s.refresh(run); return run


# ---------- GitHub ----------
def snapshot_github(max_pages: int = 10) -> ImportRun:
    """Contributors to RadixArk repos, matched to accounts by the company field; org repo counts for accounts with github_org."""
    today = date.today().isoformat()
    headers = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"} if os.environ.get("GITHUB_TOKEN") else {}
    rows, errors = [], []
    with session() as s:
        run = ImportRun(source="github", snapshot_ref=today); s.add(run); s.flush()
        accounts = s.execute(select(Account)).scalars().all()
        by_gh = {a.github_org.lower(): a for a in accounts if a.github_org}
        by_name = {a.name.lower(): a for a in accounts}
        # 1. contributors to RadixArk repos → employer match
        contributors: dict[str, dict] = {}
        for repo in RADIXARK_REPOS:
            for page in range(1, max_pages + 1):
                try:
                    batch = _get(f"https://api.github.com/repos/{repo}/contributors?per_page=100&page={page}", headers)
                except (urllib.error.URLError, OSError) as e:
                    errors.append(f"{repo} p{page}: {e}"); break
                if not batch: break
                for c in batch:
                    contributors.setdefault(c["login"], {"login": c["login"], "contributions": 0, "repos": []})
                    contributors[c["login"]]["contributions"] += c.get("contributions", 0)
                    contributors[c["login"]]["repos"].append(repo)
        matched = 0
        for login, c in list(contributors.items())[:400]:
            try:
                u = _get(f"https://api.github.com/users/{login}", headers)
            except (urllib.error.URLError, OSError) as e:
                errors.append(f"user {login}: {e}"); break
            company = (u.get("company") or "").strip().lstrip("@").lower()
            acc = by_gh.get(company) or by_name.get(company)
            rows.append({"kind": "contributor", "login": login, "company": company or None, "account_id": acc.id if acc else None,
                         "contributions": c["contributions"], "repos": c["repos"]})
            if acc: matched += 1
            time.sleep(0.1)
        # 2. org activity for accounts with a github_org
        for gh, a in list(by_gh.items()):
            try:
                o = _get(f"https://api.github.com/orgs/{gh}", headers)
                rows.append({"kind": "org", "account_id": a.id, "github_org": gh, "public_repos": o.get("public_repos"), "followers": o.get("followers")})
            except (urllib.error.URLError, OSError) as e:
                errors.append(f"org {gh}: {e}")
                if "403" in str(e) or "rate" in str(e).lower(): break
        run.added = len(rows); run.status = "ok" if not errors else ("partial" if rows else "failed")
        run.log = [f"{len(contributors)} contributors across {', '.join(RADIXARK_REPOS)}", f"{matched} matched to accounts by employer field"] + errors[:20]
        if rows: run.snapshot_ref = str(_write_snapshot("github", rows).name)
        s.commit(); s.refresh(run); return run


def latest_snapshot(source: str) -> list[dict]:
    d = ROOT / "data/sources" / source
    files = sorted(d.glob("*.jsonl")) if d.exists() else []
    if not files: return []
    return [json.loads(l) for l in files[-1].read_text().splitlines() if l.strip()]
