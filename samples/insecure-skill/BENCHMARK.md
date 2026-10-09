# TSE Benchmark Report

- **Skill ID:** `insecure-skill`
- **Version:** `0.1.0`
- **Author:** unknown
- **Skill hash:** `9530de43280590fde4decaee71370666cf5c653284add1820e4ddc36611c61d6`
- **AGL-MANIFEST:** `28b99676b2bc78f79de7509ef1bee2a4bce1bc51817f0f808d57a9446f8bb8c1`
- **Generated:** 2026-10-06T17:07:18.802497+00:00
- **Overall verdict:** **FAILED**

## Decision rationale

Tier 1 failed; later tiers were skipped.

## Tier 1 — Static & Security

- **Status:** FAILED
- **Violations:** 3

- metadata.yaml schema error at author: Field required
- Invalid TID scope 'admin.all': expected one of these prefixes: connect., tekla., projectsight., geospatial.
- Prompt injection phrase 'ignore previous instructions' detected in SKILL.md

## Tier 2 — Catalog Deduplication

- **Status:** SKIPPED

## Tier 3 — Demo Sandbox

- **Status:** SKIPPED
