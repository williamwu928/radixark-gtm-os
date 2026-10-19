# RadixArk GTM OS — review of blueprint v2 and plan v3

October 18, 2026. Reviews `blueprint-v2.md` against the new direction (FirstMark MAD, LF AI & Data, Hugging Face, Artificial Analysis, GitHub, and Baserow for the first demo). Nothing here invalidates v2's entity model, visibility rules or acceptance criteria; those stand. The changes are about stack, data sourcing, and what ships first.

## 1. The one decision that has to be made first: Baserow vs the adapted Streamlit app

v2 says "adapt the Streamlit app". The new recommendation says "Baserow for the first working demo". These are different builds, and a GitHub -> Railway deployment makes the difference concrete.

| | A. Streamlit app + Postgres (adapted v2) | B. Baserow as system of record, thin app on top | C. Baserow only, no custom app |
|---|---|---|---|
| Time to first demo | 1–2 weeks of build | Days for tables, then app on top | 1–2 days |
| Editing UI | Must be built | Free (Baserow grid/forms) | Free |
| Visibility rules (public/private before aggregation) | Fully controllable in code | Enforceable only in the app layer; Baserow views are not an authorization boundary | Not enforceable; a Baserow share link is all-or-nothing |
| Evidence model (claims, sources, supersession, contradictions) | Natural | Possible with linked tables, awkward to query | Possible, painful to keep honest |
| Overview charts / coverage matrix / drill-downs both ways | Built as designed in v2 | Built in the app, data pulled over REST | Baserow dashboards only, limited |
| Railway deployment | One service + Postgres plugin | App on Railway + Baserow Cloud (or self-host: Postgres, Redis, backend, web-frontend) | Baserow Cloud, nothing on Railway |
| Risk | Longest path to something clickable | Two systems to keep consistent; sync bugs | Cannot meet v2 acceptance criteria 6, 7, 10 |

Recommendation: **A, with SQLite locally and Postgres on Railway, and Baserow deferred.** The rules v2 cares most about (public mode must not leak private claims; unknown must not become zero; compatibility must not become customer) are rules about how data is read and aggregated, and only a code layer can enforce them on every view. Baserow is a good editing surface; it is a poor place to put the authorization and evidence logic. If no-code editing by non-engineers becomes a requirement, add Baserow in Release 2 as an *edit surface synced into* the app database, with the app still the source of truth.

If speed-to-click beats everything else for the next two weeks, choose C knowingly: a Baserow workspace with the v2 tables, shared privately, and accept that Overview, visibility and evidence provenance will be approximations until the app exists. I can build the Baserow schema from the same entity spec either way.

The rest of this plan assumes A. It changes little if B is chosen (the Baserow adapter becomes one more source adapter).

## 2. Data sources: what each one is allowed to populate

The new source list is right. The improvement is to fix, per source, which entity it may write to and what it may never write to, so that a MAD category or an HF provider mapping can never become relationship evidence by accident.

| Source | Writes to | Never writes to | Licence / access note (verify before Release 3) |
|---|---|---|---|
| FirstMark MAD | `taxonomy` (segment, category), `research_queue` (prospect suggestions) | `accounts` directly, `claims` | A curated map; bulk reuse terms unclear. Use its **category structure** as the segment taxonomy and hand-enter prospects; do not scrape the full dataset |
| LF AI & Data Landscape | `projects`, `accounts` (organizations backing projects), `aliases`, `taxonomy` | `claims` about RadixArk | Landscape data is reusable; Crunchbase-derived enrichment fields are restricted. Import `landscape.yml` / `items.csv` with an explicit field allowlist |
| Hugging Face Hub | `models`, `model_publishers`, `serving_provider_mappings`, `aliases` (HF org id) | `claims`, commercial status | Public API. Provider/model mapping and pricing fields come from the models endpoint with provider expansion; cache snapshots, rate-limit politely |
| Artificial Analysis | `provider_profiles` (pricing, latency, throughput per endpoint) | `accounts` identity, `claims` | Has terms requiring attribution; treat as enrichment on provider accounts, store snapshot date |
| GitHub API | `projects` (repos, maintainers), `aliases` (org login), `signals` (activity) | `claims`, `opportunities` | Public API with token for rate limits. Activity is a signal, displayed as such |
| Researched register (`radixark-crm-seed.json`) | `accounts`, `claims`, `sources` | nothing it does not already contain | Owned. The only source permitted to create RadixArk relationship claims |

Two consequences worth stating explicitly:

- There is exactly one write path into `claims`: the researched register and manual entry in the Intelligence view. Every external adapter is read-only with respect to relationships.
- The Overview value-chain map and coverage matrix are driven by `taxonomy`, which is a reviewed mapping table (MAD category -> LF category -> RadixArk segment), not by raw source categories. Build this mapping table first; it is what keeps the Overview from drifting as sources are added.

## 3. Changes to v2 I recommend

1. **Pull opportunity create/edit into Release 1.** v2 puts Workloads & Pipeline in Release 2, but demo narrative steps 3–4 need to *show an opportunity advancing*. Ship the opportunity form and the board in R1 against the Synthetic walkthrough dataset, keep the Researched register's pipeline empty as v2 insists. Deployment economics and reusable delivery stay in R2.
2. **The seed file is a blocker.** `radixark-crm-seed.json` (41 accounts, 46 claims) is not in this folder. The migration from its flat schema into the v2 entities is the first real engineering task and cannot be written without it. Please drop it into `data/seed/`.
3. **Private mode needs real gating the day it hits Railway.** A Railway URL is on the public internet. v2 defers authentication to "production", but the first deploy *is* exposure. Minimum for R1: a shared secret in an environment variable that unlocks Private workspace; Public mode is the default for any unauthenticated visitor; the filter runs server-side before any query, not in the UI. Proper per-user auth stays R3.
4. **Postgres from the start, SQLite for local.** v2 says SQLite for the single-user demo. Railway makes Postgres a one-click plugin, and writing the schema once with SQLAlchemy and Alembic migrations avoids a rewrite. Keep JSON import/export as v2 says.
5. **Raw observations as files under `data/sources/<source>/<date>.jsonl`.** v2 asks for raw snapshots stored unchanged. Make them files committed to the repo while small (HF and LF snapshots are a few MB) so the demo boots from the repo alone; move to a Railway volume or object storage when they grow.
6. **Add external keys to the alias table now.** `alias_type` in {display_name, domain, hf_org, github_login, lf_landscape_name, mad_name, legal_entity}. This is what lets the LF, HF and GitHub adapters resolve to the same account without prefix matching, which v2 correctly wants removed.
7. **Make visibility-leak tests the primary test class.** Every view, search, export and KPI gets a test that boots with one private-only account and one private claim and asserts they are absent in Public mode. v2 lists this as acceptance criterion 6; it should be the first test written, not the last.
8. **Drop the "Synthetic walkthrough" dataset toggle from the global header.** Keep the capability, but gate it behind the private workspace and mark every synthetic record with a visible `SYNTHETIC` badge and a separate ID prefix (`syn_`). A toggle in the header invites exactly the real/synthetic confusion v2 warns about.
9. **Scoring: ship the rubric document before the score.** `docs/rubric-v1.md` with the three assessments (commercial fit, access, evidence coverage), their inputs and the "Not assessed" rule. The UI shows rubric version and date next to any score, as v2 requires; without a written rubric there is nothing to version.

Everything else in v2 (six views, seven account tabs, the entity separations for Alibaba/Qwen and Microsoft/LinkedIn, partner initiatives referencing account IDs, the economics definitions) I would keep as written.

## 4. Repository layout

```
radixark-gtm-os/
  README.md
  pyproject.toml
  railway.toml                # start command, healthcheck
  Dockerfile
  .env.example                # DATABASE_URL, PRIVATE_WORKSPACE_SECRET, HF_TOKEN, GITHUB_TOKEN
  docs/
    blueprint-v2.md           # entity and view spec (unchanged)
    review-and-plan-v3.md     # this file
    rubric-v1.md              # scoring rubric (to write)
    taxonomy.md               # MAD/LF category -> RadixArk segment mapping
    sources.md                # per-source allowlist and licence notes
  data/
    seed/radixark-crm-seed.json      # researched register (you supply)
    seed/taxonomy.csv                # reviewed category mapping
    seed/aliases.csv                 # reviewed external keys
    sources/<source>/<date>.jsonl    # raw snapshots, unchanged
  src/gtm_os/
    app.py                    # Streamlit entry, navigation, visibility gate
    config.py
    db.py                     # SQLAlchemy engine, session, SQLite/Postgres switch
    model/                    # one module per entity group
      accounts.py  models.py  projects.py  claims.py  opportunities.py  partners.py
    adapters/                 # read-only importers, one per source
      seed.py  lf_landscape.py  huggingface.py  github.py  artificial_analysis.py  mad.py
    services/
      visibility.py           # the single place the Public/Private filter is applied
      resolution.py           # alias -> account id
      assessments.py          # rubric evaluation; returns Not assessed when inputs missing
    views/
      overview.py  accounts.py  models_projects.py  workloads.py  partners.py  intelligence.py  search.py
    ui/                       # reused widgets: pagination, KPI strip, badges, linked tables
  migrations/                 # alembic
  scripts/
    import_seed.py  snapshot_hf.py  snapshot_lf.py  snapshot_github.py
  tests/
    test_visibility.py        # leak tests, first
    test_resolution.py
    test_migration_seed.py
    test_smoke_pages.py
```

## 5. Build plan

**Phase 0 — decisions and inputs (this week)**
- Confirm stack choice (A/B/C above).
- Add `radixark-crm-seed.json` to `data/seed/`.
- Write `docs/taxonomy.md` and `docs/sources.md` (I can draft both; the taxonomy needs your review because it defines the Overview).

**Phase 1 — Release 1 skeleton (week 1–2)**
- Schema and migrations for all research entities and the CRM entities needed by R1 (accounts, aliases, models, projects, claims, sources, opportunities, contacts, activities, tasks).
- Seed migration from the flat JSON with a report of every record that could not be mapped (nothing is silently upgraded).
- Visibility service plus leak tests before any view is written.
- Views: Overview (KPI strip, value-chain map, coverage matrix, next actions), Accounts list and detail (all seven tabs, empty states), Models & Projects, Intelligence (evidence register, research queue), global search, Workloads board and opportunity form.
- Private-workspace secret gate. Dockerfile, `railway.toml`, Postgres on Railway, first deploy.

**Phase 2 — Release 2 (week 3–4)**
- Production deployments, delivery economics, reusable delivery, partner initiatives, task handoff.
- Rubric v1 implemented in `assessments.py`; scores only where all required dimensions exist.
- Optional: Baserow as a synced edit surface if non-engineers need to edit.

**Phase 3 — Release 3 (week 5+)**
- Adapters: LF landscape (field allowlist), HF models and provider mappings, GitHub orgs/repos, Artificial Analysis enrichment, MAD taxonomy import. Each produces a snapshot file plus a change set for review in Intelligence > Changes; nothing auto-overwrites.
- Real integrations only when authorized; simulations removed or clearly labelled.

## 6. Decisions taken October 18 (supersede the sections above where they conflict)

**Stack.** Option A: Streamlit, SQLAlchemy + Alembic, SQLite locally, Postgres on Railway. Baserow deferred.

**Scope cuts.**
- Workloads & Pipeline and Partners views are removed. Navigation is Overview, Accounts, Models & Projects, Intelligence, plus global search. The opportunity, deployment and partnership tables stay in the schema without a page.
- No demo or synthetic data anywhere in the product. The dataset selector is gone; the only data is the researched register plus the landscape imports.
- Accounts are categorized by **segment only**. Relationship tags, the fit assessment and the evidence-coverage column are removed from the Accounts table. Claims and sources remain in Intelligence as the audit trail and in the account's Activity & Evidence tab.
- Accounts table: Account | Segment | Vertical | Products | Scale rank | Proximity rank | Commercial status | Owner | Next action.
- Account detail tabs: Overview, Models & Stack, Ranking, People, Activity & Evidence.
- Background is white. Brand orange stays as the accent; ink stays for text.

**Account sourcing.** All companies from FirstMark MAD and the LF AI & Data landscape are imported as accounts, following the four-pass import (fetch and freeze, normalize, resolve identity, load with provenance) described in `docs/sources.md`. Landscape membership creates an account with `origin` set to the source and segment mapped through the taxonomy table; it never creates a claim. The MAD reuse licence must be confirmed before that import runs; LF is imported from `landscape.yml` with an allowlist that excludes Crunchbase-derived fields.

**Ranking.** Priority is informed by two re-queryable ranks, computed per segment on every snapshot and stored with the snapshot date (`docs/rubric-v1.md`):
- *Scale*: the segment's public volume proxy (downloads and release cadence for model developers; models served and priced endpoints for providers; supported backends for hardware; infra hiring and GitHub activity for applications and enterprises; integrations and release cadence for data/RL tooling).
- *Proximity*: distance to RadixArk's stack (employees contributing to sgl-project or Miles, SGLang support for the org's models and time-to-support, serving of SGLang-supported models, co-authored posts and day-0 announcements).
Ranks are shown within segment with their inputs and date. Neither is purchase intent; priority stays a human decision.

**Accounts view at scale.** With the register in the low thousands: server-side pagination, segment and origin filters as the main entry points, default sort by Scale rank within segment with researched accounts above landscape-only accounts; the Overview coverage matrix splits each cell into researched and landscape-only.

## 6a. Reframe, October 18 evening: RadixArk is the end user

RadixArk's own team operates this CRM. That removes two layers the earlier blueprints were built around:

- **No Public / Private workspace.** One workspace, one data set. Visibility filtering, the public-export rule and the private-only account concept are dropped from schema, views and tests. Access control is ordinary login for the team, nothing per-record.
- **No claims, evidence register or verification states.** RadixArk knows its own relationships; it does not need a third-party fact graded for confidence and visibility. What was "evidence" becomes plain **research notes** on an account: a sentence, a source link and a date, editable like any other note. No claim type, no provenance tier, no supersession, no "requires confirmation".

What replaces them:

- **Relationship status** is a field the team sets on the account (Customer, Partner, Open-source user, Prospect, None, with a date). The register's `commercial_status: Unknown` imports as "Unset" and the team fills it in. Nothing is derived from sources.
- **Intelligence becomes Research**: three tabs. *Landscape imports* (MAD and LF AI & Data runs, with the added / changed / removed accounts of each run to accept or ignore). *Signals* (the Hugging Face and GitHub snapshots that feed Scale and Proximity, with what changed since the last run). *Sources* (the links behind research notes and imports).
- Account detail tabs: Overview (identity, segment, products, relationship status, owner, next action, research notes), Models & Stack, Ranking, People, Activity.
- Accounts table: Account | Origin | Segment | Vertical | Products | Relationship status | Scale rank | Proximity rank | Owner | Next action.

Rules that still hold: landscape membership creates an account but sets no relationship status; ranks are computed from snapshots and never typed in; unknown stays unknown.

Visual: single light theme, white page background (no dark-mode variant), orange accent, ink text.

## 7. Open questions for you

1. A, B or C for the stack?
2. Where is `radixark-crm-seed.json`?
3. Is there an existing RadixArk segment taxonomy, or should I derive one from MAD/LF categories for your review?
4. Who will edit records in the next month: only you, or others? (Decides whether the shared-secret gate is enough for R1.)
5. Keep the orange/ivory/ink brand from v2 for this build?
