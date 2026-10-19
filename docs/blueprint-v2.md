# RadixArk GTM OS — blueprint v2

Revised October 18, 2026, after source inspection of williamwu928/gtm-demo-global-short-drama. This supersedes the first blueprint's recommendation to start with a separate CRM platform. It is a design and implementation specification, not a built application.

## 1. Product decision

Adapt the existing Streamlit GTM application as the demo foundation. Preserve its market intelligence -> linked account -> specific opportunity -> sales action workflow. Reuse the shared widgets, paginated tables, linked detail pages, search, parent resolution concepts and separation of refreshed research from editable CRM state. Replace the short-drama loaders, model, metrics and scoring.

Reviewed: README.md, app.py, gtm/model.py, gtm/loaders.py, gtm/config.py, gtm/scoring.py, gtm/crm.py, gtm/ui.py, gtm/integrations.py, views and smoke test structure. The original application was not rendered: the repository does not contain the required private market-data exports. Visual recommendations derive from source-defined layouts and styles.

## 2. Core user journey

Overview -> choose a segment or priority -> Accounts -> inspect product/workload evidence -> create or update a workload opportunity -> agree an evaluation -> record paid production -> assess repeatability and economics.

Secondary journey: Models & Projects -> model owner / serving provider / supported engine -> account -> assess collaboration or customer opportunity. Model support never automatically creates a customer relationship.

## 3. Navigation: six views plus global search

| Existing view | RadixArk view | User question |
|---|---|---|
| Overview | Overview | Where do we have coverage, adoption evidence and qualified commercial work? |
| Accounts | Accounts | Who is this organization, what do we know, and what is our next action? |
| Titles | Models & Projects | Who publishes or operates each model/project, and how does RadixArk connect? |
| Products | Workloads & Pipeline | What specific customer problem could become a paid deployment? |
| Studios | Partners | Which relationships supply engineering access, model access, distribution or revenue? |
| Creatives | Intelligence | What evidence supports each claim and what has changed? |
| Global search | Global search | Find accounts, models, projects, workloads, contacts and evidence. |

Do not force semantic one-to-one reuse: this is a mapping of page patterns, not a rename of the old data tables.

### Overview

Top row: researched organizations; documented product users; documented collaborators; qualified workloads; next actions due. Seed data supports only researched/evidence counts. Commercial metrics show Not assessed until real opportunities exist. Counts can overlap by relationship and must disclose this.

Section A: focused value-chain map: hardware -> clouds -> model/AI platforms -> applications/enterprises, with data/environment providers as adjacent collaborators. Highlight SGLang and Miles as cross-cutting capabilities. Selecting a category filters Accounts. Chart counts describe the researched register, not the whole industry or TAM.

Section B: segment x vertical coverage matrix. Each cell separates documented users/collaborators from proposed prospects. Empty cells mean no researched records, not zero market demand.

Section C: commercial progress: qualified workloads, paid pilots, production and expansion, counted by opportunity rather than company. Show unknown pipeline value as Unknown.

Section D: next actions and records requiring confirmation. Avoid a ranked Top opportunities chart before discovery data is available.

### Accounts

Default table: Priority | Account | Segment | Vertical | Relationship tags | Product relevance | Commercial status | Fit assessment | Evidence coverage | Owner | Next action.

Two filter rows similar to the existing application. First row: search, segment, vertical, relationship type, commercial status, owner. Second row: product, geography, buying readiness, evidence type, overdue action, public-only view. Product relevance distinguishes Confirmed use from Suggested fit.

Selecting a row opens seven tabs:
1. Overview: identity, verified facts, proposed value case, open questions and an account action panel.
2. Models & Stack: published/used models, projects, provider/hardware, deployment mode, evidence.
3. Workloads & Deals: multiple opportunities with separate stages, buyers and next actions.
4. Delivery & Economics: deployment acceptance, implementation/support effort, contribution and reusable requirements.
5. Partnerships: technical and commercial roles with separate milestones.
6. People: technical champion, budget owner, procurement and introduction route. Initially empty.
7. Activity & Evidence: chronological activity plus source-backed claims; private notes visibly marked.

Account header badges: relationship tags, commercial status, evidence provenance and owner. Never use a single Customer badge to summarize an OSS user or an organization with both free and paid workloads. Commercial status is an account summary derived from confirmed agreements, while historical statuses remain dated.

### Models & Projects

Subtabs: Models; Infrastructure projects; Serving-provider mappings.

Model fields: model ID, family/version, publisher account, modality, supported engines, support date, serving providers, source and review date. Projects have project IDs, repositories, maintainers/organizations and integration relationships. HF provider mappings and compatibility are separate from RadixArk relationships. Company, product brand, legal entity, repository organization and model family are distinct entities.

Example structure: Alibaba parent -> Qwen publisher/team -> model version; Alibaba Cloud/Bailian is a separate business unit. Microsoft and LinkedIn remain distinct operating accounts with an explicit corporate relationship. Never collapse subsidiaries just because a parent is known.

### Workloads & Pipeline

Subtabs: Opportunities; Production deployments; Reusable delivery.

List/board columns: opportunity | account | workload | product | stage | buyer/budget status | evidence | owner | next milestone. Initial stage remains unset until an actual opportunity is created.

Typical workflow: Discovery -> Qualified workload -> Evaluation scoped -> Paid pilot -> Production contracting -> Production live. Permit unpaid evaluation, direct-to-production and other documented paths. Closed lost, Disqualified and Nurture are explicit outcomes. Expansion creates a new opportunity under the same account.

Opportunity detail: pain; why now; current approach; paid offer; proposed package; buyer; budget; baseline; acceptance criteria; technical scope; customer/RadixArk responsibilities; commercial terms; next step and accountable owner. SGLang, Miles, support and endpoint offerings may be combined, subject to confirmed availability.

Production detail: model/version, hardware/cloud, traffic and SLOs, integration requirements, operating ownership, implementation effort and ongoing support. Reusable delivery tracks recurring requirements, templates, integration modules, documentation and approved customization. Distinguish requested capability, delivered capability and roadmap proposal.

### Partners

All organizations remain in Accounts. Partner records reference account IDs; do not copy accounts into a disconnected partner database.

Partner types: hardware; model launch; cloud; channel; data/environment; integration. Track objective, direction of value/payment, early access scope if confirmed, technical owner, commercial owner, milestone and evidence. Sourced revenue and influenced revenue are separate and should not be double-counted. An investor or event participant is not automatically a commercial partner.

Suggested views: hardware enablement; model-launch collaboration; cloud distribution; data/RL ecosystem. Account roles may overlap with supplier or competitive roles only when supported.

### Intelligence

Subtabs: Evidence register; Research queue; Changes; Sources.

Every claim links to a source and specifies subject, relationship type, product/workload context, publication date when available, review date, provenance, confidence, visibility and supersession state. New source snapshots create changes, not overwrites of the old record. Contradictory claims remain visible for resolution. A last-reviewed date is not a last-customer-contact date.

Research queue: proposed account, hypothesized segment/fit, supporting source, missing facts, assigned researcher and next action. Nothing in the queue is counted as qualified pipeline.

## 4. Data architecture

Preserve the original project's division between rebuildable research and human-maintained CRM data.

Research: accounts, account aliases/hierarchy, models, projects, organizations/projects/models relationships, evidence claims, sources and observation snapshots.

CRM: opportunities, contacts, activities, deployments, partnership initiatives, tasks and manual assessment overrides.

Use durable internal account IDs with an explicit alias table. Domain and parent relationships help resolution but cannot be the only identity key. Research reloads must preserve IDs and never overwrite stage, owner, contacts, tasks or human notes. Handle merges through explicit reviewed mappings and redirects. Store raw source observations unchanged with retrieval metadata; normalize into linked entities separately.

For the first single-user demo, adapt the existing persisted-state abstraction to SQLite with transactions and schema versioning, leaving JSON as import/export. For shared production use, choose a managed database and proper user authentication. A single JSON file is not a multi-user concurrency strategy. No migration or live service is implemented by this blueprint.

## 5. What to reuse / adapt / replace

| Module or pattern | Decision |
|---|---|
| app.py navigation and sidebar | Reuse pattern; replace page registry and branding |
| gtm/ui.py | Reuse pagination, KPI, badges, table selection, linked navigation and chart patterns; update styles and empty states |
| gtm/normalize.py and parent mapping | Adapt identity-resolution ideas; replace short-drama vocabulary and prefix matching with reviewed AI entity aliases |
| gtm/loaders.py | Replace filename-driven private XLSX dependencies with source adapters and curated seed imports |
| gtm/model.py | Rebuild linked AI entities; preserve source provenance and explicit join confidence |
| gtm/scoring.py | Replace creative-scale/momentum scoring and rank-based P0 assignment |
| gtm/crm.py | Reuse CRUD separation; add workload and partnership records plus transactional persistence |
| gtm/views/accounts.py | Reuse list/detail/tab layout and action panel; opportunity-level stages |
| gtm/integrations.py | Hide until implemented, or clearly label simulation. Existing HubSpot/Salesforce/Calendly actions are demos |
| gtm/security.py | Reassess for this data model. Page-count gating is not sufficient to separate public facts and private interview/contact data |
| tests/smoke_pages.py | Adapt page rendering, navigation and access checks to seed-only boot and evidence-level visibility |

## 6. Scoring and recommendation design

The old app calculates scores from measured market exports. The RadixArk register mostly has relationship evidence, so its weights are not portable.

Display three distinct assessments:
- Commercial fit: workload fit, customer pain, budget readiness, repeatability and strategic value.
- Access: known introduction path and buyer access, not assumption of intent.
- Evidence coverage: which required discovery fields have support, source recency and contradictory claims.

Initially show Not assessed. Unknown is not zero. Only publish a composite score after the required dimensions are assessed under a documented rubric. Show component rationale, missing evidence, rubric version and date. Priority is an explicit, reviewable decision; do not automatically label the first eight accounts P0. Keep partner strategic value separate from direct customer economics.

Recommendations should say Proposed entry use case / Reason to investigate / Facts to confirm. A high download count, funding round or introduction is not confirmed compute spend, production demand or purchase intent.

## 7. Customer and seller economics

Customer: cost per successful task, successful task count, quality threshold, completion time and human intervention. Include failed attempts without counting the same retry twice. Compare at equivalent evaluation conditions.

RadixArk: one-time pilot/implementation revenue and costs; recurring contract revenue, matched-period compute and support costs; contribution. Separate usage revenue, software/support fees and pass-through compute. Unknown inputs keep outputs Unknown. Partnerships use separate technical/launch/distribution milestones and attributed commercial results.

## 8. Evidence, public/private and demo mode

Dataset selector: Researched register / Synthetic walkthrough. Researched register starts from the existing 41 accounts and 46 claims, with no invented contacts, opportunities, owners or amounts. Synthetic data, if later added, must be explicitly marked, isolated from real accounts and excluded from real metrics.

Visibility selector: Public / Private workspace. Apply visibility filtering before aggregation, filtering, search, table construction, exports and detail rendering. Private-only prospects and counts must not leak into public mode. Preserve authorization on every view; hidden buttons are not authorization. The first-three-pages paywall pattern can be optional presentation behavior but cannot be the private-data boundary.

Brand: orange #D55816, warm ivory #F8F2EA, ink #0C0B0A. Keep the reference's analytical layout: compact KPI strip, clear section dividers, generous main table and side action panel. Public evidence, interview-reported claims and hypotheses need distinct labels, not merely different colors.

## 9. Prioritized scope

Release 1: seed-only boot; Overview; Accounts detail; Models & Projects; Intelligence; search; private/public filtering; preserved edits. Show empty commercial sections cleanly.

Release 2: Workloads & Pipeline; paid-offer and pilot acceptance fields; deployment/economics; task and handoff workflow; Partners initiatives.

Release 3: permitted source adapters, refresh snapshots, change review and real integrations when authorized. Start with curated sources, then HF and GitHub APIs; use MAD/LF taxonomy as permitted, not as relationship evidence.

## 10. Acceptance criteria

- App starts with curated seed data only; no private short-drama XLSX files required.
- One account can have several relationships and independently staged opportunities.
- Compatibility/event/investor claims never become paying-customer status automatically.
- Source refresh preserves manual state and stable links.
- Unknown values do not become zeros or pseudo-precise scores.
- Public mode excludes private claims, private-only accounts and their counts in every view.
- Account/model/workload/partner drill-downs resolve both ways and search respects visibility.
- Commercial totals use actual opportunities and distinct recurring/one-time amounts.
- Repeated delivery requirements can be linked to multiple deployments.
- Real integrations and synthetic simulations are visibly distinguishable.

## 11. Suggested demo narrative

1. Start at the industry map and select enterprise financial services.
2. Open a proposed New York prospect; show what is known versus unvalidated.
3. Inspect the workload hypothesis, paid-offer questions and relevant product capabilities.
4. Show how a qualified opportunity would advance with buyer and acceptance evidence; keep real-data pipeline empty until validated.
5. Switch to a publicly documented Miles user to demonstrate a different evidence status, without implying payment.
6. Finish with the delivery-economics and reusable-product structure that turns discovery into a scalable commercial process.

## Reference

Repository reviewed: https://github.com/williamwu928/gtm-demo-global-short-drama — inspected checkout `379fd0f`.

Retain radixark-crm-seed.json as the researched input register. Its original flat schema requires migration into the entities above; no source claims are upgraded during migration.
