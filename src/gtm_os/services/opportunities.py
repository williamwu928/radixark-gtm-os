"""Account intelligence in the existing database; imports never overwrite CRM edits."""
from sqlalchemy import select
from gtm_os.db import Account, Opportunity, Note, session

SEGMENTS = ["AI Model Labs", "AI-native Applications", "Enterprise AI Teams", "GPU Clouds & Inference Providers", "Chipmakers", "Hyperscalers", "Unclassified"]
STAGES = ["Research", "Qualified", "Engaged", "Pilot", "Production"]
TYPES = ["Customer", "Partner", "Both"]
COLORS = dict(zip(STAGES, ["#667085", "#2563eb", "#9333ea", "#b45309", "#15803d"]))
SEGMENT_MAP = {"models": SEGMENTS[0], "applications": SEGMENTS[1], "enterprise": SEGMENTS[2], "cloud": SEGMENTS[3], "hardware": SEGMENTS[4]}

# Existing researched account IDs. These are proposed discovery topics, not buying signals.
CURATED = [
    ("ACC-007", 0, "Large-model inference", "Test whether batching and KV-cache optimization can reduce serving cost at a fixed latency target.", "Head of inference", "Customer"),
    ("ACC-035", 0, "Multilingual model serving", "Explore deployment portability and cost per token across accelerator backends.", "Inference platform lead", "Both"),
    ("ACC-013", 1, "Customer-support agents", "Assess whether long-context agent sessions need tighter tail latency and tenant isolation.", "VP Engineering", "Customer"),
    ("ACC-022", 1, "Streaming voice generation", "Investigate time-to-first-audio and concurrency requirements for production voice workloads.", "Head of speech infrastructure", "Customer"),
    ("ACC-030", 2, "Internal research assistants", "Explore a private retrieval and inference evaluation with auditable data handling.", "AI platform lead", "Customer"),
    ("ACC-031", 2, "Research compute workflows", "Validate whether shared inference capacity can improve utilization for internal research teams.", "Head of research engineering", "Customer"),
    ("ACC-016", 3, "GPU inference fleet", "Explore a joint benchmark of model serving throughput, utilization and operational reliability.", "VP Product, GPU cloud", "Both"),
    ("ACC-034", 3, "Dedicated GPU clusters", "Investigate a serving integration for customers moving from reserved GPUs to managed inference.", "Head of strategic partnerships", "Partner"),
    ("ACC-003", 4, "Accelerator runtime integration", "Assess a technical collaboration on representative inference kernels and reproducible benchmarks.", "Inference ecosystem lead", "Partner"),
    ("ACC-005", 4, "Alternative accelerator deployment", "Evaluate model coverage, kernel gaps and performance portability on the accelerator software stack.", "AI software alliances lead", "Partner"),
    ("ACC-001", 5, "Cloud inference integration", "Explore whether a portable serving integration could support enterprise deployment requirements.", "Cloud AI partner engineering", "Partner"),
    ("ACC-002", 5, "Enterprise AI serving", "Investigate a joint validation path for private networking, observability and model deployment.", "AI platform partner lead", "Partner"),
]


def segment_for(account):
    # Landscape categories are proposals, not reliable commercial classifications.
    if account.origin != "researched":
        return "Unclassified"
    if account.id in {"ACC-001", "ACC-002", "ACC-024", "ACC-004", "ACC-019", "ACC-019P"}:
        return "Hyperscalers"
    return SEGMENT_MAP.get(account.segment_id, "Unclassified")


def initialize():
    """Insert missing curated hypotheses only. Never modify accounts or existing opportunities."""
    with session() as s:
        for aid, seg, workload, hypothesis, role, typ in CURATED:
            if s.get(Account, aid) and not s.get(Opportunity, aid):
                s.add(Opportunity(account_id=aid, icp_segment=SEGMENTS[seg], workload=workload,
                    hypothesis=hypothesis, opportunity_type=typ, stage="Research", basis="Hypothesis",
                    details={"buyer_role": role, "warm_path": "Identify a mutual connection or public partner channel; introduction not confirmed.",
                             "problem": hypothesis, "solution": "Propose a scoped technical discovery and benchmark after confirming the need.",
                             "suggested_action": f"Validate the workload and identify the {role.lower()} before proposing a benchmark."}))
        s.commit()


def rows(query="", segment="", opportunity_type="", stage="", sort="Account"):
    with session() as s:
        records = s.execute(select(Account, Opportunity).outerjoin(Opportunity, Opportunity.account_id == Account.id)).all()
        research = {}
        for note in s.scalars(select(Note).order_by(Note.date.desc(), Note.id.desc())):
            research.setdefault(note.account_id, "Research: " + note.text)
        result = []
        for a, o in records:
            icp = o.icp_segment if o else segment_for(a)
            current_stage = o.stage if o else "Research"
            typ = o.opportunity_type if o else ""
            hypothesis = o.hypothesis if o else ""
            if query and query.casefold() not in f"{a.name} {hypothesis}".casefold(): continue
            if segment and segment != icp: continue
            if opportunity_type and opportunity_type != typ: continue
            if stage and stage != current_stage: continue
            d = (o.details or {}) if o else {}
            result.append({"id": a.id, "Account": a.name, "ICP Segment": icp,
                "Workload": o.workload if o else "", "Opportunity": hypothesis,
                "Opportunity Type": typ, "Trigger / Evidence": (o.evidence if o else "") or research.get(a.id, ""),
                "Stage": current_stage, "Contact / Warm Path": d.get("contact") or d.get("warm_path", ""),
                "Next Action": a.next_action or d.get("suggested_action", ""), "Owner": a.owner or "Unassigned",
                "Due Date": a.next_action_due})
        if sort == "Stage": result.sort(key=lambda r: (STAGES.index(r["Stage"]), r["Account"].casefold()))
        elif sort == "Due Date": result.sort(key=lambda r: (r[sort] is None, r[sort], r["Account"]))
        else: result.sort(key=lambda r: (r[sort].casefold(), r["Account"].casefold()))
        return result


def save(aid, *, name, website, owner, next_action, due, segment, workload, hypothesis, opportunity_type, stage, basis, evidence, details):
    if not name.strip(): raise ValueError("Account name is required.")
    if segment not in SEGMENTS or stage not in STAGES or opportunity_type not in [""] + TYPES or basis not in ["Hypothesis", "Evidence-backed"]:
        raise ValueError("Invalid classification.")
    if basis == "Evidence-backed" and not evidence.strip(): raise ValueError("Describe the supporting evidence before marking an opportunity evidence-backed.")
    with session() as s:
        a = s.get(Account, aid)
        if a is None: raise ValueError("Account no longer exists.")
        o = s.get(Opportunity, aid)
        if o is None:
            o = Opportunity(account_id=aid)
            s.add(o)
        a.name, a.homepage, a.owner = name.strip(), website.strip() or None, owner.strip() or None
        a.next_action, a.next_action_due = next_action.strip() or None, due
        o.icp_segment, o.workload, o.hypothesis = segment, workload, hypothesis
        details = dict(details)
        details.pop("suggested_action", None)  # An intentionally cleared action must stay cleared.
        o.opportunity_type, o.stage, o.basis, o.evidence, o.details = opportunity_type, stage, basis, evidence, details
        s.commit()
