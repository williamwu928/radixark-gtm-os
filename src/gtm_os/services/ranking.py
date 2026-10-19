"""Rubric v1: Scale and Proximity ranks, computed per segment from the latest snapshots.

An account with no inputs gets no rank row ("Not computed"). An account with
some inputs is ranked on those and lists the missing ones. Ranks are never
compared across segments and never edited by hand.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import delete, select

from gtm_os.adapters.signals import latest_snapshot
from gtm_os.db import Account, ModelRecord, Note, Rank, session

RUBRIC = "v1"
SCALE_INPUTS = {
    "hardware": ["supported_backends", "runnable_families"],
    "cloud": ["models_served", "priced_endpoints"],
    "models": ["hf_downloads_30d", "hf_models_90d", "hf_providers"],
    "data": ["pt_integrations", "gh_stars", "gh_releases_90d"],
    "platform": ["catalogue_size", "partner_program"],
    "applications": ["open_ml_roles", "gh_public_repos"],
    "enterprise": ["open_ml_roles", "gh_public_repos"],
    "oss_foundation": ["gh_public_repos"],
}
PROXIMITY_INPUTS = ["contributors", "sglang_supported_models", "serves_sglang_models", "coauthored_posts"]


def _percentile(values: dict[str, float]) -> dict[str, float]:
    if not values: return {}
    ordered = sorted(values.values())
    n = len(ordered)
    return {k: (sum(1 for x in ordered if x < v) + 0.5 * sum(1 for x in ordered if x == v)) / n for k, v in values.items()}


def compute_ranks() -> dict:
    today = date.today().isoformat()
    gh = latest_snapshot("github")
    with session() as s:
        accounts = s.execute(select(Account)).scalars().all()
        models = s.execute(select(ModelRecord)).scalars().all()
        notes = s.execute(select(Note)).scalars().all()
        # ---- gather raw inputs per account ----
        raw: dict[str, dict] = defaultdict(dict)
        per_pub: dict[str, list[ModelRecord]] = defaultdict(list)
        for m in models:
            if m.publisher_account_id: per_pub[m.publisher_account_id].append(m)
        for aid, ms in per_pub.items():
            raw[aid]["hf_downloads_30d"] = sum(m.downloads_30d or 0 for m in ms)
            raw[aid]["hf_models_90d"] = sum(1 for m in ms if m.created_at and (date.today() - date.fromisoformat(m.created_at[:10])).days <= 90)
            raw[aid]["hf_providers"] = len({p for m in ms for p in (m.providers or [])})
            raw[aid]["sglang_supported_models"] = sum(1 for m in ms if m.sglang_supported)
        contrib = defaultdict(int)
        for r in gh:
            if r.get("kind") == "contributor" and r.get("account_id"): contrib[r["account_id"]] += 1
            if r.get("kind") == "org" and r.get("public_repos") is not None: raw[r["account_id"]]["gh_public_repos"] = r["public_repos"]
        for aid, n in contrib.items(): raw[aid]["contributors"] = n
        for n in notes:
            t = n.text.lower()
            if any(k in t for k in ("coauthor", "collaborat", "day-0", "day 0", "launch")):
                raw[n.account_id]["coauthored_posts"] = raw[n.account_id].get("coauthored_posts", 0) + 1
        # ---- Scale: percentile within segment per input, averaged ----
        s.execute(delete(Rank).where(Rank.rubric == RUBRIC))
        by_seg = defaultdict(list)
        for a in accounts: by_seg[a.segment_id].append(a)
        computed = 0
        for seg, accs in by_seg.items():
            inputs = SCALE_INPUTS.get(seg, [])
            pct = {inp: _percentile({a.id: raw[a.id][inp] for a in accs if inp in raw[a.id]}) for inp in inputs}
            scores = {}
            for a in accs:
                have = [pct[inp][a.id] for inp in inputs if a.id in pct[inp]]
                if have: scores[a.id] = sum(have) / len(have)
            ordered = sorted(scores, key=lambda k: -scores[k])
            for i, aid in enumerate(ordered, 1):
                s.add(Rank(account_id=aid, kind="scale", rank=i, of=len(ordered), score=round(scores[aid], 3), rubric=RUBRIC, snapshot_date=today,
                           inputs={k: raw[aid][k] for k in inputs if k in raw[aid]}, missing=[k for k in inputs if k not in raw[aid]]))
                computed += 1
            # ---- Proximity: count of input families present, then rank ----
            prox = {a.id: sum(1 for k in PROXIMITY_INPUTS if raw[a.id].get(k)) for a in accs if any(raw[a.id].get(k) for k in PROXIMITY_INPUTS)}
            ordered = sorted(prox, key=lambda k: (-prox[k], -raw[k].get("contributors", 0)))
            for i, aid in enumerate(ordered, 1):
                s.add(Rank(account_id=aid, kind="proximity", rank=i, of=len(ordered), score=prox[aid], rubric=RUBRIC, snapshot_date=today,
                           inputs={k: raw[aid][k] for k in PROXIMITY_INPUTS if raw[aid].get(k)}, missing=[k for k in PROXIMITY_INPUTS if not raw[aid].get(k)]))
        s.commit()
        return {"accounts_with_inputs": len([a for a in accounts if raw[a.id]]), "scale_ranks": computed, "snapshot_date": today}
