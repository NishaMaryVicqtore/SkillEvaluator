---
name: validate-booking-rules
description: Verify AI-generated booking or shuttle code aligns with backend/rules.js and booking-policies.md before merge.
---

# Validate booking rules skill

Use when implementing or reviewing booking, cancellation, no-show, or capacity features in Trimble WorkRide.

## When to use

- Adding or changing book/cancel endpoints, including `POST /api/chat/bookings`
- Modifying `Book.jsx`, `Chat.jsx`, `MyBookings.jsx`, or `Admin.jsx`
- Editing `backend/rules.js` or booking-related store logic

## Procedure

1. Read `backend/rules.js` and `.ai-governance/rules/booking-policies.md`.
2. Confirm cutoff times match:
   - Morning: book by 8 PM **previous day**
   - Evening: book by 3 PM **same day**
3. Confirm cancel window: **1 hour before** slot start.
4. Confirm no-show block: **2 consecutive** → blocked **1 day** on the Book page and `POST /api/bookings` (can still sign in). The chat exception is **PRD change — urgent chat override** below and is owned by `validate-chat-override`.
5. Ensure weekend/holiday checks use `isBookableDate()`.
6. Run `npm run skills:eval` and check this skill's cases pass (cutoff boundary, blocked user, cancel window).

## Output checklist

Report to the PR or chat:

- [ ] Cutoffs implemented in backend (not UI-only)
- [ ] Cancel rule matches `canCancel()`
- [ ] No-show block matches `isUserBlocked()`
- [ ] Web book still matches `isUserBlocked()` with no override
- [ ] Chat responses name this skill on the no-show block, bookable date, cutoff, and one-booking-per-date steps of `decision_trace`
- [ ] No invented slot times or capacity limits
- [ ] User-facing error messages match API reasons

## PRD change — urgent chat override

Source: `prd/workride-chat-prd.md`. Baseline `prd/workride-prd.md` stays as written.

Old line: **2 consecutive no-shows, blocked 1 day, no exception.**

New line, chat only: a blocked employee may book from `POST /api/chat/bookings` when `validateUrgentOverride()` accepts `urgent_category` of `medical_emergency`, `family_emergency`, or `client_visit` and an explanation of 15–500 characters. The Book page and `POST /api/bookings` still refuse the booking.

The full procedure and checklist for this exception are in `.ai-governance/skills/validate-chat-override/SKILL.md`.

## Evaluation

Test cases are in `evals.json` next to this file. Run them with `npm run skills:eval`.

## Do not

- Hard-code different cutoff times in the frontend
- Allow booking on weekends/holidays without updating `rules.js`
- Skip blocked-user checks on `POST /api/bookings`
- Let the Book page or `POST /api/bookings` accept an urgent override
- Accept an urgent category other than `medical_emergency`, `family_emergency`, or `client_visit`
