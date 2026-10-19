# Ranking rubric v1 — Scale and Proximity

Draft, October 18, 2026. Two ranks per account, computed per segment from re-queryable public signals on every snapshot. Each stored rank carries rubric version, snapshot date and its inputs. Priority (P0–P3) remains a human field; the ranks inform it.

## Scale — the segment's volume proxy

| Segment | Inputs | Source |
|---|---|---|
| Hardware and accelerators | Serving frameworks with a supported backend; model families runnable on the platform | SGLang, vLLM, TensorRT docs; HF hardware tags |
| Hyperscalers and GPU clouds | Models served; endpoints with published pricing; throughput coverage | HF inference-provider mappings; Artificial Analysis |
| Model developers and AI labs | 30-day downloads summed across the org; models published in the last 90 days; serving providers carrying the org's models | Hugging Face API |
| Data, RL environments and sandboxes | Integrations with post-training frameworks; GitHub stars; releases in the last 90 days | GitHub API, framework docs |
| Enterprise data and AI platforms | Model-catalogue size; partner-program size | Vendor docs; HF mappings |
| AI application companies | Open ML/infra roles; engineering headcount growth; HF and GitHub org presence | Job boards; GitHub API; LF enrichment where licensed |
| Enterprise model operators | Open ML-platform and LLM-inference roles; public model deployments | Job boards; public statements |

Normalization: each input is converted to a percentile within the segment, inputs are averaged with equal weight in v1, and the result is reported as a rank (1 = largest) and a decile. An account missing an input is ranked on the inputs it has and shows which are missing. An account with no inputs shows "Not computed", never a rank.

## Proximity — distance to RadixArk's stack

Inputs, all segments:
- Employees contributing to sgl-project or Miles (GitHub profile employer matched to the account's aliases); count and recency
- Org's models on the SGLang supported list, and days from model release to support
- Serves SGLang-supported models via HF inference-provider mappings
- Co-authored posts, day-0 announcements, event listings (from the researched register's claims, public only)

Scored 0–4 by count of input families present, then ranked within segment. Shown as a rank and the list of satisfied inputs.

## Display

- A 2×2 on the Overview: Scale × Proximity per segment, with counts in each quadrant.
- Accounts table: Scale rank and Proximity rank columns, sortable, with the snapshot date in the column header.
- Account detail, Ranking tab: both ranks, every input with its value, source and retrieval date, and the inputs that are missing.

## Rules

- Ranks are recomputed from snapshots, never edited by hand.
- Ranks are never compared across segments.
- No input is treated as purchase intent or compute spend.
- Landscape membership (MAD, LF) is not an input to either rank.
