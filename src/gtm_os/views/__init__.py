"""Shared view helpers."""
from __future__ import annotations
import json
import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from ..models import Account, Segment, Rank
from ..services import ranking

CSS = """
<style>
.block-container{padding-top:1.2rem;max-width:1400px}
h1{font-size:1.4rem!important;font-weight:600!important;margin-bottom:.2rem!important}
h2{font-size:.8rem!important;font-weight:600!important;letter-spacing:.06em;text-transform:uppercase;color:#6B645E;border-bottom:1px solid #E6E2DD;padding-bottom:4px;margin-top:1.4rem!important}
h3{font-size:1rem!important;font-weight:600!important}
.sub{color:#6B645E;margin:0 0 .8rem}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:#E6E2DD;border:1px solid #E6E2DD;margin:.4rem 0 .8rem}
.kpi{background:#fff;padding:10px 12px}.kpi .n{font-size:24px;font-weight:600;line-height:1.1}.kpi .n.na{font-size:14px;color:#6B645E;font-weight:500}.kpi .l{font-size:12px;color:#6B645E;margin-top:2px}
.pill{display:inline-block;font-size:11px;padding:2px 7px;border-radius:999px;border:1px solid #CBC5BD;margin:1px 3px 1px 0;white-space:nowrap}
.pill.prod{background:#FBE6DA;border-color:transparent}.pill.na{color:#6B645E;border-color:#E6E2DD}
.unk{color:#6B645E;font-style:italic}
.rn{border-left:3px solid #CBC5BD;padding:8px 10px;background:#fff;margin-bottom:6px}.rn .m{font-size:11px;color:#6B645E;font-family:ui-monospace,Menlo,monospace}
.empty{padding:18px;border:1px dashed #CBC5BD;color:#6B645E;text-align:center;background:#fff;border-radius:4px}
.empty b{color:#0C0B0A;display:block;margin-bottom:4px}
.note{font-size:12px;color:#6B645E}
[data-testid="stSidebar"]{background:#F6F4F1}
</style>
"""


def kpis(items):
    html = "".join(f'<div class="kpi"><div class="n {"na" if na else ""}">{n}</div><div class="l">{l}</div></div>' for n, l, na in items)
    st.markdown(f'<div class="kpis">{html}</div>', unsafe_allow_html=True)


def empty(title, text):
    st.markdown(f'<div class="empty"><b>{title}</b>{text}</div>', unsafe_allow_html=True)


def segments(s) -> dict[str, Segment]:
    return {x.id: x for x in s.scalars(select(Segment).order_by(Segment.sort_order))}


def fmt_rank(r: Rank | None) -> str:
    return f"{r.rank} / {r.of}" if r else "Not computed"


def rank_detail(r: Rank | None, kind: str) -> str:
    if not r:
        return "Not computed"
    used = json.loads(r.inputs or "{}"); missing = json.loads(r.missing or "[]")
    parts = [f"{ranking.LABELS.get(k, k)}: {v:,.0f}" for k, v in used.items()]
    txt = f"**{r.rank} of {r.of}** in segment · snapshot {r.snapshot_date}  \n" + "; ".join(parts)
    if missing:
        txt += f"  \nMissing: {', '.join(ranking.LABELS.get(m, m) for m in missing)}"
    return txt


def go_account(account_id: str):
    st.session_state["account_id"] = account_id
    st.session_state["view"] = "Accounts"
    st.rerun()


def load_account(s, account_id: str) -> Account | None:
    return s.scalar(select(Account).where(Account.id == account_id).options(
        selectinload(Account.products), selectinload(Account.notes), selectinload(Account.contacts), selectinload(Account.activities), selectinload(Account.aliases)))
