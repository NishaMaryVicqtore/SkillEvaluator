# Booking policy rules

All booking, cancellation, and no-show logic must match `backend/rules.js`. Agents must not invent alternate business rules in UI or API code.

## Booking cutoffs

| Slot type | Times | Book by |
|-----------|-------|---------|
| Morning (Metro → Office) | 7:30, 8:30 | **8:00 PM previous evening** |
| Evening (Office → Metro) | 5:00 PM, 6:00 PM | **3:00 PM same day** |

Implementation reference: `getBookingCutoff()` and `isPastBookingCutoff()` in `backend/rules.js`.

## Cancellation

- Allowed until **1 hour before** slot start time
- Implementation reference: `canCancel()` in `backend/rules.js`
- UI must surface the same constraint (see `MyBookings.jsx`)

## No-show policy

- **2 consecutive no-shows** → user can sign in but **cannot book for 1 day**
- The Book page and `POST /api/bookings` keep this hard block. They do not accept an urgent override.
- Chat only (`POST /api/chat/bookings`): a blocked employee may book one trip when `validateUrgentOverride()` accepts `medical_emergency`, `family_emergency`, or `client_visit` plus an explanation of 15–500 characters. `blocked_until` stays in place. Source: `prd/workride-chat-prd.md`.
- Implementation reference: `getConsecutiveNoShows()`, `updateBlockIfNeeded()`, `isUserBlocked()`, `validateUrgentOverride()` in `backend/rules.js`

## Capacity and booking limits

- Default: **10 confirmed + 5 waitlist** per slot (see server/store configuration)
- Advance booking: up to **30 calendar days**
- Up to **2 bookings per date** (different slots)

## Non-bookable dates

- Weekends and listed public holidays in `backend/rules.js` (`isBookableDate()`)
- Do not add booking UI for dates the backend rejects

## Where to implement changes

1. Update `backend/rules.js` first (source of truth)
2. Enforce in `backend/server.js` API handlers
3. Mirror validation messages in frontend for UX only—not as sole enforcement

## Concrete failure example (ungoverned)

An agent implemented "cancel anytime before slot start" in the React page while the API still enforced the 1-hour rule. Users saw confusing errors and support tickets increased.

**Governed outcome:** Agent reads this file and `rules.js` before changing Book or MyBookings flows.
