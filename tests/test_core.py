from datetime import date
from pathlib import Path
import pytest
from sqlalchemy import select, func
from gtm_os import config, bootstrap
from gtm_os.db import session
from gtm_os.models import Account, Note, Project, ImportChange, ImportRun, Rank
from gtm_os.services import crm, ranking
from gtm_os.services.resolution import norm_name, Resolver, Candidate
from gtm_os.adapters import seed, landscape, signals


@pytest.fixture(scope="module", autouse=True)
def booted():
    bootstrap.ensure_seeded()


def test_seed_import_shape():
    with session() as s:
        assert s.scalar(select(func.count(Account.id)).where(Account.origin == "Researched")) == 42  # 41 + Alibaba parent
        assert s.scalar(select(func.count(Note.id)).where(Note.seed_ref != None)) == 46  # noqa: E711
        bu = s.get(Account, "ACC-019"); assert bu.parent_id == "ACC-P01" and "Bailian" in bu.name
        assert s.get(Account, "ACC-006").parent_id == "ACC-002"
        assert all(a.relationship_status == "Unset" for a in s.scalars(select(Account)))


def test_seed_import_is_idempotent_and_keeps_crm_fields():
    with session() as s:
        crm.update_account(s, "ACC-003", relationship_status="Partner", owner="Test Owner", priority="P1", next_action="Call")
        seed.run(s)
        a = s.get(Account, "ACC-003")
        assert (a.relationship_status, a.owner, a.priority, a.next_action) == ("Partner", "Test Owner", "P1", "Call")
        assert s.scalar(select(func.count(Note.id)).where(Note.seed_ref != None)) == 46  # noqa: E711


def test_landscape_import_resolution():
    with session() as s:
        assert s.scalar(select(func.count(Account.id)).where(Account.origin == "LF AI & Data")) > 90
        assert s.scalar(select(func.count(Project.id)).where(Project.origin == "LF AI & Data")) > 300
        run = s.scalar(select(ImportRun).where(ImportRun.source == "lfai"))
        matched = {c.source_name: c.entity_id for c in s.scalars(select(ImportChange).where(ImportChange.run_id == run.id, ImportChange.kind == "matched"))}
        assert matched["International Business Machines Corporation"] == "ACC-014"
        assert matched["IBM (hosting)"] == "ACC-014"
        assert matched["Advanced Micro Devices (AMD)"] == "ACC-005"
        assert matched["Intel(hosting)"] == "ACC-023"
        # landscape membership never sets CRM state
        assert all(a.relationship_status == "Unset" and a.owner is None for a in s.scalars(select(Account).where(Account.origin == "LF AI & Data")))


def test_landscape_rerun_adds_nothing():
    with session() as s:
        before = s.scalar(select(func.count(Account.id)))
        run = landscape.run(s, "lfai", sorted((config.SOURCES_DIR / "lfai").glob("*.yml"))[-1])
        assert run.added == 0
        assert s.scalar(select(func.count(Account.id))) == before


def test_norm_and_near_miss():
    assert norm_name("NVIDIA Corporation") == norm_name("Nvidia")
    assert norm_name("Meta (hosting)") == "meta"
    with session() as s:
        r = Resolver(s)
        assert r.resolve(Candidate("Alibaba Cloud (Singapore) Private LTD")).kind in ("review", "matched")
        assert r.resolve(Candidate("Totally New Startup XYZ")).kind == "new"


def test_ranking_from_metrics():
    with session() as s:
        d = date.today()
        signals._put(s, "ACC-037", "scale.hf_downloads_30d", 100, "t", d)
        signals._put(s, "ACC-020", "scale.hf_downloads_30d", 10, "t", d)
        signals._put(s, "ACC-020", "prox.contributors", 3, "t", d)
        signals._put(s, "ACC-020", "prox.coauthored", 1, "t", d)
        s.commit()
        ranking.compute(s)
        rk = ranking.ranks_for(s, ["ACC-037", "ACC-020", "ACC-001"])
        assert rk["ACC-037"]["scale"].rank == 1 and rk["ACC-020"]["scale"].rank == 2
        assert rk["ACC-020"]["proximity"].score == 2
        assert "scale" not in rk.get("ACC-001", {})  # no inputs → not computed


def test_crm_writes():
    with session() as s:
        crm.add_note(s, "ACC-001", "Test note", "https://example.com", "tester")
        crm.add_contact(s, "ACC-001", name="Jane", title="Eng", role="Technical champion", email="", owner="", notes="")
        crm.add_activity(s, "ACC-001", "Call", "Spoke", "me", "Follow up", date.today())
        a = s.get(Account, "ACC-001")
        assert a.next_action == "Follow up" and len(a.contacts) == 1 and any(n.text == "Test note" for n in a.notes)
