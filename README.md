# GTM-OS-IC

Account Intelligence & Opportunity Tracker: a single searchable account table with a compact editor for technical context, opportunity hypotheses, buyers and next actions.

## Run locally

Use Python 3.12 or later:

```sh
pip install -r requirements.txt
streamlit run src/gtm_os/app.py
```

The active entry point uses `gtm_os.db` and `services/importer.py`. Older modular views, adapters and `models.py` remain for historical reference; the deployed app does not use them. Tests target the active implementation.

## Data and editing

One configured database holds the existing account register, source research and the new `account_opportunities` table. Account IDs, original classifications, research, contacts, activities and importer history are preserved. Each account can have one current opportunity. Six ICP categories plus Unclassified are available. Search, category/type/stage filters, stage colors, due-date sorting and an account detail editor are included.

Twelve curated hypotheses cover two accounts per primary category. They begin at Research and contain proposed discovery topics and buyer roles, not invented contacts, buying signals or commercial relationships. Initialization inserts only missing opportunity records and never overwrites edits. There is no demo mode, separate dataset, reset control, scoring, live API dependency or outbound messaging.

Existing source evidence is available in each account's Source research panel. Additional profile and commercial notes are separate from imported source records. Existing owner and next-action fields remain authoritative. Missing owner assignments display Unassigned.

## Database and deployment

`DATABASE_URL` selects the same backend as before: SQLite locally, PostgreSQL when configured. `APP_PASSWORD` retains the existing team-password gate; without it, the app retains its existing open-access behavior. No environment variables or Railway service settings are changed by this release.

The upgrade adds only `account_opportunities`, keyed by the existing account ID, with ICP segment, workload, hypothesis, type, stage, evidence basis, evidence text, profile/execution JSON and update timestamp. No existing table is dropped or rebuilt. Before first upgrading an existing database, a backup is written to `GTM_BACKUP_DIR` (default `data/backups`): SQLite database copy, or a gzipped logical table-data snapshot for PostgreSQL. Startup stops if backup creation fails. PostgreSQL snapshots are data exports, not substitutes for managed database backups; files in an ephemeral container require copying out for long-term retention.

Keep the existing Dockerfile and Railway configuration. Railway must already be connected to this repository's main branch with automatic deployment enabled. Merge to main triggers that configured integration; GitHub code publication alone does not prove a successful Railway rollout. Health endpoint: `/_stcore/health`.

## Tests

```sh
pip install pytest
python -m pytest -q
```

Coverage includes real entry-point rendering, import idempotence, preserved research, six-category hypothesis initialization, search/filters/sorting, editor saves and fresh-session persistence, authentication and SQLite upgrade backup. Tests use a local test database, not the deployed database.

## Limits

One current opportunity per account; edits occur in the detail form, not inline. No opportunity change audit log or conflict-resolution UI. Source classifications remain unchanged; uncertain landscape classifications stay Unclassified. The existing password gate is shared-team access, not role-based access. PostgreSQL backup/upgrade requires validation in the deployed environment. No new infrastructure is introduced.
