"""Human-maintained CRM writes. These are the only code paths that change relationship status,
owner, priority, next action, notes, contacts and activities."""
from __future__ import annotations
from datetime import date
from sqlalchemy.orm import Session
from ..models import Account, Note, Contact, Activity, AccountProduct


def update_account(s: Session, account_id: str, **fields) -> Account:
    a = s.get(Account, account_id)
    allowed = {"relationship_status", "status_date", "owner", "priority", "next_action", "next_action_due", "segment_id", "vertical"}
    for k, v in fields.items():
        if k in allowed:
            setattr(a, k, v if v not in ("", None) else None if k not in ("relationship_status", "priority") else "Unset")
    if "relationship_status" in fields and a.status_date is None:
        a.status_date = date.today()
    s.commit()
    return a


def set_products(s: Session, account_id: str, product_ids: list[str]):
    a = s.get(Account, account_id)
    have = {p.product_id for p in a.products}
    for p in a.products[:]:
        if p.product_id not in product_ids:
            s.delete(p)
    for pid in product_ids:
        if pid not in have:
            s.add(AccountProduct(account_id=account_id, product_id=pid))
    s.commit()


def add_note(s: Session, account_id: str, text: str, source_url: str | None, author: str | None) -> Note:
    n = Note(account_id=account_id, text=text.strip(), source_url=source_url or None, author=author or None, date=date.today())
    s.add(n); s.commit()
    return n


def add_contact(s: Session, account_id: str, **f) -> Contact:
    c = Contact(account_id=account_id, **{k: (v or None) for k, v in f.items()})
    s.add(c); s.commit()
    return c


def add_activity(s: Session, account_id: str, type: str, summary: str, owner: str | None, next_action: str | None, due: date | None) -> Activity:
    act = Activity(account_id=account_id, type=type, summary=summary.strip(), owner=owner or None, next_action=next_action or None, due=due)
    s.add(act)
    if next_action:
        a = s.get(Account, account_id)
        a.next_action = next_action; a.next_action_due = due
        if owner and not a.owner:
            a.owner = owner
    s.commit()
    return act
