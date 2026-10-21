"""Core invariants for the ORM and importers used by the deployed entry point."""
from sqlalchemy import func, select
from gtm_os.db import Account, Note, Project, session
from gtm_os.services.importer import bootstrap, import_seed, import_lfai, latest_lfai_snapshot, norm_name, Resolver


def test_seed_shape_and_research_preserved():
    bootstrap()
    with session() as s:
        assert s.scalar(select(func.count(Account.id)).where(Account.origin == 'researched')) == 42
        assert s.scalar(select(func.count(Note.id))) >= 46
        assert s.get(Account, 'ACC-019').parent_id == 'ACC-019P'
        assert s.get(Account, 'ACC-006').parent_id == 'ACC-002'


def test_seed_idempotence_preserves_crm():
    with session() as s:
        a=s.get(Account, 'ACC-003'); a.owner='Core test owner'; a.next_action='Confirm workload'; s.commit()
        counts=(s.scalar(select(func.count(Account.id))), s.scalar(select(func.count(Note.id))))
    import_seed()
    with session() as s:
        a=s.get(Account, 'ACC-003')
        assert (a.owner,a.next_action)==('Core test owner','Confirm workload')
        assert counts==(s.scalar(select(func.count(Account.id))),s.scalar(select(func.count(Note.id))))


def test_landscape_idempotence():
    if latest_lfai_snapshot():
        with session() as s:
            counts=(s.scalar(select(func.count(Account.id))),s.scalar(select(func.count(Project.id))))
        import_lfai()
        with session() as s:
            assert counts==(s.scalar(select(func.count(Account.id))),s.scalar(select(func.count(Project.id))))
            assert all(a.relationship_status == 'Unset' for a in s.scalars(select(Account).where(Account.origin == 'lfai')))


def test_identity_resolution():
    assert norm_name('NVIDIA Corporation') == norm_name('Nvidia')
    with session() as s:
        resolver=Resolver(s)
        assert resolver.resolve(name='NVIDIA')[0]=='ACC-003'
        assert resolver.resolve(name='Totally New Startup XYZ') == (None,None)
