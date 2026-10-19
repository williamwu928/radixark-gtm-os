# Seed register check — `data/seed/radixark-crm-seed.json`

Checked October 18, 2026. 41 accounts, 46 claims, 13 sources (12 public, 1 private `CALL`). Every account has at least one claim; relationship tags match claim types on every account; contacts, opportunities, deployments, activities and partnerships are empty, as the register's rules require.

The file is the researched register and stays untouched. The points below are handled in the migration (`scripts/import_seed.py`), not by editing the JSON.

## Derived at import

1. **Account visibility.** 11 accounts have only private claims: Intel, AWS, Mercor, Reflection AI, Databricks, Snowflake, Cohere, D. E. Shaw, Two Sigma, Bridgewater, Ramp. They get `visibility = private` and are absent from every Public-mode view, count, search and export. The other 30 are public.
2. **Relationship tags are derived from claims**, not stored on the account. The register stores both and they agree today; the app keeps one source of truth so a new claim cannot leave the tag stale. A private claim's tag is itself private.
3. **`commercial_status`** stays `Unknown` for all 41; the UI renders it as Unknown, never blank or zero.
4. **Fields not in the declared schema** (`commercial_status_basis`, `engagement_stage`, `account_value`) are all null and are dropped. `priority`, `owner`, `region` are null and stay null (Not assessed / Unassigned).

## Entity splits the register does not yet make

5. **Alibaba (ACC-019).** Stored as one account with `business_unit = Bailian`. The import creates `Alibaba` (parent, no claims) and keeps ACC-019 as `Alibaba Cloud / Bailian` with `parent_account_id` pointing to it, so the Step 5 claim stays on the business unit. Qwen is added as a model publisher only when a claim or an HF import references it.
6. **Microsoft (ACC-002) / LinkedIn (ACC-006).** Both stay operating accounts; LinkedIn gets `parent_account_id = ACC-002` as a corporate link. Nothing is collapsed.
7. **NVIDIA (ACC-003) and AMD (ACC-005)** are named as investors in S1 inside the claim text. The import adds a separate `Investor (announcement)` relationship tag from that sentence so it cannot be read as customer or partner evidence; it does not create a partnership record.
8. **DigitalOcean (ACC-017).** Direction is RadixArk as the customer. Tagged `Supplier`; counted under collaborators, never under product users.

## Reference tables created from the register

9. `segments` (7) become the segment taxonomy; MAD/LF categories map onto these.
10. `products`: SGLang, Miles, SGLang-Omni (from EV-022). Account `products` arrays become account–product links with `relevance = Confirmed use` only where a `Documented product user` claim exists; otherwise `Suggested fit`.
11. `verticals` are free text today (Search and recommendation, Scientific AI, Agent automation, Customer support, Voice and audio, Hedge funds, Fintech). They become a reviewed list; nulls stay null.
12. `models` and `projects` referenced inside claim text (Step 5, Kimi K3, Drama 3, EAGLE-3, OME, Vertex AI) are **not** auto-created from prose. They enter the Models & Projects view through the research queue or an HF/GitHub import, linked back to the claim.
13. Sources S2 and S7 share a URL with different types; both are kept as distinct source records.

## Import report

The import prints every record it derived or split (items 1, 5, 6, 7) so each decision is reviewable. No claim is upgraded.
