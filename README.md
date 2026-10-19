# RadixArk GTM OS

CRM and go-to-market workspace for RadixArk: researched accounts, model/provider relationships, evidence-backed claims, workload opportunities and partner initiatives.

Status: planning. See `docs/blueprint-v2.md` (entity and view specification) and `docs/review-and-plan-v3.md` (stack decision, data-source rules and build plan).

## Principles

- Research data is rebuildable from sources; CRM data is human-maintained and never overwritten by a refresh.
- Only the researched register and manual entry can create relationship claims. External sources (LF AI & Data, Hugging Face, GitHub, Artificial Analysis, MAD) enrich accounts, models and projects but never assert a RadixArk relationship.
- Public mode never shows private claims or private-only accounts, in any view, count, search or export.
- Unknown stays Unknown. No score is shown until its rubric inputs exist.

## Planned stack

Python, Streamlit, SQLAlchemy + Alembic, SQLite locally, Postgres on Railway. Baserow deferred (see plan, section 1).

## Layout

See `docs/review-and-plan-v3.md`, section 4.
