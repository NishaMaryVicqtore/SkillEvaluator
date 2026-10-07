# Tangled design

## Objectives

The objective is unclear.

## Scope

Scope is everything.

## Modules

- billing
- payments
- ledger
- legacy

```mermaid
flowchart LR
  billing --> payments
  payments --> ledger
  ledger --> billing
  billing --> ledger
  payments --> billing
  ledger --> payments
```

## Integrations

None recorded.

## Data design

No data design.

## Security

No threat model.

## Non-functional requirements

None.

## Risks

Unknown.

## API

No contract.
