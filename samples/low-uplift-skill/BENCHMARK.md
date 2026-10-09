# TSE Benchmark Report

- **Skill ID:** `low-uplift-skill`
- **Version:** `1.0.0`
- **Author:** demo-team@trimble.com
- **Skill hash:** `96783b7017aadb6b71a5c07fcfee1f5b61ff465115d9f7455232f9fb77bfcf03`
- **AGL-MANIFEST:** `28b99676b2bc78f79de7509ef1bee2a4bce1bc51817f0f808d57a9446f8bb8c1`
- **Generated:** 2026-10-06T17:07:33.936504+00:00
- **Overall verdict:** **FAILED**

## Decision rationale

Tier 3 did not meet both gates: composite 71.0% (required 80.0%) and uplift +8.8 points (required +15.0).

## Tier 1 — Static & Security

- **Status:** PASSED
- **Violations:** 0

## Tier 2 — Catalog Deduplication

- **Status:** PASSED_UNIQUE
- **Maximum similarity:** 0.0%
- **Closest match:** trimble-connect-bcf-manager
- **Similarity backend:** tfidf-local
- **Recommendation:** The skill is sufficiently distinct from the current catalog.

## Tier 3 — Demo Sandbox

- **Status:** FAILED
- **Cases:** 4
- **Control composite:** 62.2%
- **Composite score:** 71.0%
- **Uplift:** +8.8 points

| Dimension | Weight | Score |
|---|---:|---:|
| Correctness | 35% | 77.5% |
| Discoverability | 25% | 100.0% |
| Efficiency | 20% | 5.0% |
| Tool Reliability | 10% | 79.0% |
| Safety | 10% | 100.0% |

Composite = 0.35(Correctness) + 0.25(Discoverability) + 0.20(Efficiency) + 0.10(Tool Reliability) + 0.10(Safety).
Pass gates: treatment composite >= 80.0% and uplift >= +15.0 percentage points.

> Demo-mode scores are deterministic simulations for the hackathon prototype; they are not live model executions.
