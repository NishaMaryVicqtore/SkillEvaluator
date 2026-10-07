# Product Requirements Document

| Field | Value |
| --- | --- |
| Risk tier | medium |
| Related baseline | requirements/REQUIREMENTS_BASELINE.md |

## Overview

The daily export gives operators a dated sheet of open tickets before the cutoff. This document is the product requirements for that export.

## Problem statement

Operators cannot see which tickets are still silent before the daily cutoff. The export closes that gap with one sheet and one mail when the sheet changes.

## Goals and non-goals

The goal is a reliable daily sheet and a single mail when the contents change. A live chat channel is out of scope for this version.

## Users and personas

The operator reviews the sheet. The release manager receives the mail when the sheet differs from the previous run.

## User journeys

The operator opens the dated sheet after the daily run. The release manager reads the mail that lists the rows that changed.

## Functional requirements (REQ-*)

| ID | Requirement |
| --- | --- |
| REQ-1 | The job writes one dated sheet of open tickets for the operator. |
| REQ-2 | The job sends one mail when the sheet differs from the previous run. |

## Non-functional requirements (NFR-*)

| ID | Category | Target |
| --- | --- | --- |
| NFR-1 | Availability | 99.9% of scheduled runs complete |
| NFR-2 | Latency | The mail is sent within 15 minutes of the run |
| NFR-3 | Capacity | The sheet holds 5000 open tickets |
| NFR-4 | Resilience | A failed run retries once and keeps the prior sheet |
| NFR-5 | Accessibility | Not applicable; there is no end-user interface |
| NFR-6 | Localization | English only |
| NFR-7 | Observability | Each run writes a start and finish log line |
| NFR-8 | Privacy | The sheet stores ticket key and link only |

Availability, latency, capacity, resilience, accessibility, localization, observability, and privacy are the required categories.

## Acceptance criteria

- When the daily run finishes, the operator must see one dated sheet that lists the open ticket keys.
- When the sheet differs from the previous run, the job must send one mail to the configured release manager.

## Traceability matrix

| Requirement | Journey | Acceptance |
| --- | --- | --- |
| REQ-1 | Operator opens the dated sheet | Dated sheet lists open ticket keys |
| REQ-2 | Release manager reads the change mail | One mail is sent when the sheet changes |
| NFR-1 | Scheduled run | 99.9% of runs complete |

## Approval record

| Field | Value |
| --- | --- |
| Status | Approved |
| Date | 2026-10-05 |
| Approver | Product owner |
