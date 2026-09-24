# Changelog

## 0.04.3 — 2026-09-24

- Made Copy week suggest the next week from a populated schedule, or the displayed target from a blank week using the latest earlier scheduled source.
- Added scheduled-source selection and a configurable one-or-more-week target offset; open the first copied week and retain conflict highlights.

## 0.04.2 — 2026-09-24

- Added one-at-a-time publish conflict review with eligible replacement candidates, home-team priority and Skip.
- Extended Copy week to repeat at a chosen weekly, monthly or yearly interval and count; preview checks all target weeks and batch application is atomic.

## 0.04.1 — 2026-09-24

- Added Copy week with source selection, preview, conflict warnings and an explicit target-draft replacement choice.
- Preserved local wall-clock times across DST and carried Coverage plus shift details together.
- Added confirmation before resetting a draft.

## 0.04 — 2026-09-23

- Added week navigation, published-week selection and immutable publication snapshots with revision comparisons. Drafts for different weeks now coexist.
- Added time off, sick call and actual standby call-out records, affected shift flags and publish checks.
- Added editable shift role, location, unpaid break minutes and notes.
- Added basic event history and PostgreSQL backup/restore instructions.

## 0.03 — 2026-09-23

- Simplified Teams management into an all-team list with people and recurring-period counts; removed redundant team/week filters and schedule status on that page.
- Added team-name search and people search by name, team, or skill.
- Consolidated the future release plan in `ROADMAP.md`.
- Added the Skills management section to the future requirements.

## 0.02 — 2026-09-23

- Added a vertical On-call contact list with both staffed and standby assignments, handoff details, and missing phone indicators.
- Added casual employee availability calendars, dated `.ics` import/export, and a preview for duplicates and unavailability conflicts.
- Introduced a translation boundary for On-call labels and date formatting; broader interface localization remains future work.
- Added future work for user accounts and self-service availability, schedule emails, and Microsoft Teams Shifts Excel export.
- Added a database migration for positive availability windows.

## Earlier private alpha

- Added independent Coverage requirements and employee Schedule shifts, team and person editing, scheduling checks, and publish blockers highlighted on affected shifts.
- Set the default web bind address to `0.0.0.0` for LAN access.
