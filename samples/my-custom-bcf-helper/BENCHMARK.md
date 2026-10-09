# TSE Benchmark Report

- **Skill ID:** `my-custom-bcf-helper`
- **Version:** `1.0.0`
- **Author:** demo-team@trimble.com
- **Skill hash:** `b2f3cc0b2f84c4dd79f4ae7cedecf2692b048baa274c369f43c0b357b3a3ccbe`
- **AGL-MANIFEST:** `28b99676b2bc78f79de7509ef1bee2a4bce1bc51817f0f808d57a9446f8bb8c1`
- **Generated:** 2026-10-06T17:07:33.962634+00:00
- **Overall verdict:** **FAILED**

## Decision rationale

Tier 2 rejected the skill as a duplicate of trimble-connect-bcf-manager.

## Tier 1 — Static & Security

- **Status:** PASSED
- **Violations:** 0

## Tier 2 — Catalog Deduplication

- **Status:** REJECTED_DUPLICATE
- **Maximum similarity:** 100.0%
- **Closest match:** trimble-connect-bcf-manager
- **Similarity backend:** tfidf-local
- **Recommendation:** Reject: Skill is 100% similar to existing skill 'trimble-connect-bcf-manager'. Do not create a duplicate skill; submit an update PR to 'trimble-connect-bcf-manager' instead.

## Tier 3 — Demo Sandbox

- **Status:** PASSED
- **Cases:** 4
- **Control composite:** 49.9%
- **Composite score:** 90.9%
- **Uplift:** +41.0 points

| Dimension | Weight | Score |
|---|---:|---:|
| Correctness | 35% | 97.0% |
| Discoverability | 25% | 100.0% |
| Efficiency | 20% | 62.1% |
| Tool Reliability | 10% | 96.0% |
| Safety | 10% | 99.2% |

Composite = 0.35(Correctness) + 0.25(Discoverability) + 0.20(Efficiency) + 0.10(Tool Reliability) + 0.10(Safety).
Pass gates: treatment composite >= 80.0% and uplift >= +15.0 percentage points.

> Demo-mode scores are deterministic simulations for the hackathon prototype; they are not live model executions.
