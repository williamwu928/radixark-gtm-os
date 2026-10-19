"""Smoke tests: imports are idempotent and every view renders without exceptions."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ["DATABASE_URL"] = f"sqlite:///{ROOT / 'data' / 'test.db'}"
os.environ.pop("APP_PASSWORD", None)

from sqlalchemy import func, select  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

from gtm_os.db import Account, ImportChange, Project, session  # noqa: E402
from gtm_os.services.importer import bootstrap, import_lfai, import_seed, latest_lfai_snapshot  # noqa: E402
from gtm_os.services.ranking import compute_ranks  # noqa: E402

(ROOT / "data" / "test.db").unlink(missing_ok=True)
APP = str(ROOT / "src/gtm_os/app.py")


def test_bootstrap_and_idempotent_imports():
    bootstrap()
    with session() as s:
        n1 = s.scalar(select(func.count(Account.id))); p1 = s.scalar(select(func.count(Project.id)))
        assert n1 >= 41 and p1 >= 3
        assert s.get(Account, "ACC-019").parent_id == "ACC-019P"
        assert s.get(Account, "ACC-006").parent_id == "ACC-002"
        # CRM edit survives a re-import
        a = s.get(Account, "ACC-001"); a.relationship_status = "Partner"; a.owner = "test"; s.commit()
    import_seed()
    if latest_lfai_snapshot(): import_lfai()
    with session() as s:
        assert s.scalar(select(func.count(Account.id))) == n1
        a = s.get(Account, "ACC-001"); assert a.relationship_status == "Partner" and a.owner == "test"
        assert s.scalar(select(func.count(ImportChange.id)).where(ImportChange.kind == "review")) >= 0


def test_ranks_do_not_invent():
    r = compute_ranks()
    assert r["scale_ranks"] == 0  # no HF/GitHub snapshot in tests → no scale rank, never a zero


def _run(page=None, acct=None):
    at = AppTest.from_file(APP, default_timeout=60)
    if page: at.session_state["page"] = page
    if acct: at.session_state["acct"] = acct
    at.run()
    assert not at.exception, [str(e) for e in at.exception]
    return at


def test_overview_renders():
    at = _run("Overview"); assert any("Overview" in t.value for t in at.title)


def test_accounts_renders():
    at = _run("Accounts"); assert at.dataframe


def test_account_detail_renders():
    at = _run("Accounts", "ACC-019"); assert any("Alibaba" in t.value for t in at.title)


def test_models_and_research_render():
    _run("Models & Projects"); _run("Research")
