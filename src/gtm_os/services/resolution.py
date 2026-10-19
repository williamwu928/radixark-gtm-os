"""Identity resolution: map a candidate organization from any source onto an existing account.

Order: exact alias → homepage domain → GitHub org → normalized name. A near-miss on name
(prefix / suffix like "Nvidia Corp") is reported for review, never auto-merged.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import Account, AccountAlias

STOP = {"inc", "inc.", "corp", "corp.", "corporation", "co", "co.", "ltd", "ltd.", "llc", "ai", "labs", "lab",
        "the", "technologies", "technology", "software", "cloud", "foundation", "group", "holdings", "limited", "gmbh", "sa", "ag"}


def norm_name(name: str) -> str:
    name = re.sub(r"\s*\(?\bhosting\)?\s*$", "", name, flags=re.I)   # "IBM (hosting)", "Intel(hosting)"
    name = re.sub(r"\s*\([^)]*\)", "", name)                            # drop parentheticals
    s = re.sub(r"[^a-z0-9 ]+", " ", name.lower())
    words = [w for w in s.split() if w not in STOP]
    return " ".join(words) or s.strip()


def domain_of(url: str | None) -> str | None:
    if not url:
        return None
    if "://" not in url:
        url = "https://" + url
    host = urlparse(url).netloc.lower().split(":")[0]
    host = re.sub(r"^www\.", "", host)
    return host or None


def github_org_of(repo_url: str | None) -> str | None:
    if not repo_url:
        return None
    m = re.search(r"github\.com/([^/\s]+)", repo_url)
    return m.group(1).lower() if m else None


@dataclass
class Candidate:
    name: str
    homepage: str | None = None
    repo_url: str | None = None
    crunchbase: str | None = None
    extra_aliases: list[tuple[str, str]] = field(default_factory=list)

    @property
    def domain(self):
        return domain_of(self.homepage)

    @property
    def github_org(self):
        return github_org_of(self.repo_url)


@dataclass
class Resolution:
    kind: str                 # matched | review | new
    account: Account | None = None
    how: str | None = None


class Resolver:
    def __init__(self, s: Session):
        self.s = s
        self._alias: dict[tuple[str, str], str] = {}
        self._by_norm: dict[str, str] = {}
        for a in s.scalars(select(AccountAlias)):
            self._alias[(a.alias_type, a.value.lower())] = a.account_id
        for acc in s.scalars(select(Account)):
            self._by_norm.setdefault(norm_name(acc.name), acc.id)
            if acc.domain:
                self._alias.setdefault(("domain", acc.domain.lower()), acc.id)
            if acc.github_org:
                self._alias.setdefault(("github_login", acc.github_org.lower()), acc.id)

    def _acc(self, aid):
        return self.s.get(Account, aid)

    def resolve(self, c: Candidate) -> Resolution:
        for t, v in [("display_name", c.name)] + c.extra_aliases:
            aid = self._alias.get((t, v.lower()))
            if aid:
                return Resolution("matched", self._acc(aid), f"alias:{t}")
        if c.domain:
            aid = self._alias.get(("domain", c.domain))
            if aid:
                return Resolution("matched", self._acc(aid), "domain")
        if c.github_org:
            aid = self._alias.get(("github_login", c.github_org))
            if aid:
                return Resolution("matched", self._acc(aid), "github_org")
        n = norm_name(c.name)
        aid = self._by_norm.get(n)
        if aid:
            return Resolution("matched", self._acc(aid), "name")
        m = re.search(r"\(([A-Za-z0-9 .&-]{2,40})\)", c.name)          # "Advanced Micro Devices (AMD)"
        if m and "hosting" not in m.group(1).lower():
            aid = self._alias.get(("display_name", m.group(1).lower())) or self._by_norm.get(norm_name(m.group(1)))
            if aid:
                return Resolution("matched", self._acc(aid), "acronym")
        # near miss: one normalized name is a word-prefix of the other
        for other, oid in self._by_norm.items():
            if other and n and (n.startswith(other + " ") or other.startswith(n + " ")):
                return Resolution("review", self._acc(oid), f"near:{other}")
        return Resolution("new")

    def register(self, acc: Account, c: Candidate, source_tag: str):
        """Add the candidate's identifiers as aliases of an account."""
        pairs = [(source_tag, c.name), ("display_name", c.name)]
        if c.domain:
            pairs.append(("domain", c.domain))
        if c.github_org:
            pairs.append(("github_login", c.github_org))
        if c.crunchbase:
            pairs.append(("crunchbase", c.crunchbase))
        for t, v in pairs + c.extra_aliases:
            key = (t, v.lower())
            if key in self._alias:
                continue
            self.s.add(AccountAlias(account_id=acc.id, alias_type=t, value=v))
            self._alias[key] = acc.id
        self._by_norm.setdefault(norm_name(acc.name), acc.id)
        if not acc.domain and c.domain:
            acc.domain = c.domain
        if not acc.github_org and c.github_org:
            acc.github_org = c.github_org
        if not acc.homepage and c.homepage:
            acc.homepage = c.homepage
