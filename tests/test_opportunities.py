"""Persistent CRM workflow and safety regression tests."""
from datetime import date
from pathlib import Path
import pytest
from sqlalchemy import select, func, create_engine, inspect
from streamlit.testing.v1 import AppTest
from gtm_os.db import Account, Opportunity, Note, session, _backup_before_crm_upgrade
from gtm_os.services.importer import bootstrap, import_seed
from gtm_os.services import opportunities as crm

APP=str(Path(__file__).resolve().parents[1]/'src/gtm_os/app.py')

@pytest.fixture(autouse=True)
def ready():
    bootstrap(); crm.initialize()


def test_curated_are_hypotheses_and_cover_six_segments():
    with session() as s:
        items=[s.get(Opportunity, r[0]) for r in crm.CURATED]
        assert len(items)==12 and all(items)
        assert len({o.icp_segment for o in items})==6
        assert all(o.stage=='Research' and o.basis=='Hypothesis' for o in items)
        assert not any(o.details.get('contact') for o in items)


def test_filters_and_sorting():
    assert crm.rows(query='Decagon')[0]['id']=='ACC-013'
    assert crm.rows(query='tail latency')[0]['id']=='ACC-013'
    assert not crm.rows(query='no such company qwerty')
    for segment in crm.SEGMENTS[:6]:
        assert len(crm.rows(segment=segment))>=2
    for typ in crm.TYPES:
        assert all(r['Opportunity Type']==typ for r in crm.rows(opportunity_type=typ))
    assert not crm.rows(stage='Pilot')
    assert all(r['Stage']=='Research' for r in crm.rows(stage='Research'))
    for sort in ['Account','ICP Segment','Stage','Due Date']: assert crm.rows(sort=sort)


def test_edit_refresh_and_import_preserves_research():
    at=AppTest.from_file(APP,default_timeout=120)
    at.session_state['acct']='ACC-013'; at.run()
    assert not at.exception
    with session() as s:
        before=[(n.id,n.text) for n in s.scalars(select(Note).where(Note.account_id=='ACC-013'))]
        source_segment=s.get(Account,'ACC-013').segment_id
    next(w for w in at.text_input if w.label=='Owner').set_value('Workflow test owner')
    next(w for w in at.text_area if w.label=='Next action').set_value('Schedule technical discovery')
    next(w for w in at.selectbox if w.label=='Stage').select('Qualified')
    next(w for w in at.date_input if w.label=='Due date').set_value(date(2026,11,15))
    next(b for b in at.button if b.label=='Save').click().run()
    assert not at.exception
    crm.initialize(); import_seed()
    refreshed=AppTest.from_file(APP,default_timeout=120)
    refreshed.session_state['acct']='ACC-013'; refreshed.run()
    assert not refreshed.exception
    assert next(w for w in refreshed.text_input if w.label=='Owner').value=='Workflow test owner'
    assert next(w for w in refreshed.selectbox if w.label=='Stage').value=='Qualified'
    assert crm.rows(stage='Qualified',query='Decagon')[0]['Due Date']==date(2026,11,15)
    with session() as s:
        assert before==[(n.id,n.text) for n in s.scalars(select(Note).where(Note.account_id=='ACC-013'))]
        assert s.get(Account,'ACC-013').segment_id==source_segment
    next(b for b in refreshed.button if b.label=='← Accounts').click().run()
    assert not refreshed.exception and refreshed.dataframe


def test_password_gate(monkeypatch):
    monkeypatch.setenv('APP_PASSWORD','test-only-password')
    at=AppTest.from_file(APP,default_timeout=120).run()
    assert not at.dataframe and not at.exception
    at.text_input[0].set_value('wrong'); at.button[0].click().run()
    assert at.error and not at.dataframe
    at.text_input[0].set_value('test-only-password'); at.button[0].click().run()
    assert at.dataframe and not at.exception


def test_table_has_no_old_navigation_or_labels():
    at=AppTest.from_file(APP,default_timeout=120).run()
    assert not at.exception and not at.radio
    assert at.title[0].value=='GTM-OS-IC'
    columns=list(at.dataframe[0].value.columns)
    assert 'Scale rank' not in columns and 'Opportunity' in columns
    at.text_input(key='search').set_value('no such company qwerty').run()
    assert not at.dataframe and at.info


def test_upgrade_backs_up_existing_sqlite(tmp_path,monkeypatch):
    import sqlite3
    database=tmp_path/'before.db'
    with sqlite3.connect(database) as c:
        c.execute('CREATE TABLE accounts (id TEXT PRIMARY KEY)')
        c.execute("INSERT INTO accounts VALUES ('existing')")
    monkeypatch.setenv('GTM_BACKUP_DIR',str(tmp_path/'backups'))
    eng=create_engine(f'sqlite:///{database}')
    _backup_before_crm_upgrade(eng)
    copies=list((tmp_path/'backups').glob('*.db'))
    assert len(copies)==1
    with sqlite3.connect(copies[0]) as c: assert c.execute('SELECT id FROM accounts').fetchone()==('existing',)
    assert 'account_opportunities' not in inspect(eng).get_table_names()
    eng.dispose()
