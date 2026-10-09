# TSE Benchmark Report

- **Skill ID:** `trimble-connect-bcf-manager`
- **Version:** `0.1.0`
- **Author:** core-ai@trimble.com
- **Skill hash:** `64809580e13bcb6b5fb3d96277dab2f5abd13aa2e488270beea03d48a54ea795`
- **AGL-MANIFEST:** `N/A`
- **Generated:** 2026-10-09T05:41:46.162379+00:00
- **Overall verdict:** **PASSED VERIFIED SKILL**

## Decision rationale

Version update met the previous 85.0% Tier 3 baseline with 90.9%.

## Tier 1 — Static & Security

- **Status:** PASSED
- **Violations:** 0

## Tier 2 — Catalog Deduplication

- **Status:** VERSION_UPDATE
- **Maximum similarity:** 100.0%
- **Closest match:** trimble-connect-bcf-manager
- **Similarity backend:** catalog-id
- **Recommendation:** Compare this update with version 0.0.9; Tier 3 must not regress below 85.0%.
- **Previous version:** 0.0.9
- **Previous Tier 3 baseline:** 85.0%

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
