# Coverage Scheduler roadmap

Release numbers are product labels (`0.03`, `0.04`, …). Each release has its own ZIP and changelog. A feature is complete only after its interface, persistence, permissions, and relevant checks are reviewed. Scope and order may change before implementation.

## 0.02 — accepted baseline

Casual availability calendar and dated ICS import/export; published On-call contact list for staffed and standby shifts; early localization boundary.

## 0.03 — Teams and People usability

Show all teams in a simple management list. Search teams by name and people by name, team, or skill. Keep the selected-team filter for scheduling views. No new scheduling rules.

## 0.04 — Schedule timeline and records (alpha delivered)

Browse previous published and future schedules with clear draft/published states. Retain publication versions and compare changes with actor and time. Model breaks, location, role, notes, and overnight shifts. Record time off, sick calls, and actual on-call call-outs; show affected coverage and replacement options. Add an audit trail, permission review for private contact/availability data, and backup/restore procedure with a restore test. The alpha delivers event history with a generic administrator actor and written backup/restore steps; a restore drill and per-user permissions await an operational environment and 0.07 accounts. Break duration is informational until exact break windows are modelled.

## 0.04.1 — Carry forward a schedule (alpha delivered)

Copy a prior draft or published week into a new reviewable draft, including Coverage and assignments. Preview conflicts and require explicit replacement of an existing target draft.

## 0.04.2 — Conflict review and recurring copies (alpha delivered)

Review publish-blocking shifts one at a time with eligible replacements and Skip; repeat a source schedule into multiple draft weeks at weekly, monthly or yearly intervals with a batch preview and explicit replacement.

## 0.04.3 — Contextual copy defaults (alpha delivered)

Copy the displayed schedule into the next week by default. When the displayed week is empty, select the most recent earlier scheduled week and target the displayed week. Allow another source week and a target one or more weeks later, with preview and conflict highlighting.

## 0.05 — Scheduler workspace

Make automatic scheduling an explicit workflow rather than a hidden Create draft action. Add team and individual preferred shift durations and patterns (for example 8-hour, 10-hour, or 12-hour shifts); keep allowed minimum/maximum durations as separate hard settings. Compare feasible durations against coverage and explain when the scheduler chooses a less-preferred length. This is distinct from the existing preference for grouping on-call periods. Show candidate shifts, hard-rule exclusions, conflicts, uncovered intervals, selection reasons, and alternatives before publication. Add coverage-by-hour/skill and workload-balance metrics. Show the predicted effect of advice before applying a suggestion; keep manager control over publication. Scheduler settings should default to assigning a team’s own qualified people to its Coverage before borrowing from another team. Make the preference strength configurable. A cross-team assignment remains possible when home-team staff are unavailable or it materially improves coverage, but show the source-team impact and explain the move; avoid unnecessary team transfers.

## 0.06 — Skills and data onboarding

Dedicated Skills management, person qualifications (including verification and expiry), Coverage requirements, and visible qualification gaps. Block unqualified assignment while retaining historical records. Import teams, people, skills, coverage templates, and existing shifts with validation and preview for organizations with 20–100 teams.

## 0.07 — Accounts and self-service

Employee invitation/registration and management, manager/team roles, administrator recovery, and employee editing of their own availability. Make Active Directory or Microsoft Entra sign-in and group-to-role mapping an optional integration; retain local accounts. Deactivation must revoke access while preserving historical schedules. Audit permission changes.

## 0.08 — Regional policy and scheduling analysis

Region in person details and at the team/work location. Distinguish an employee's eligible region from the location of a shift. Settings control display of regional advisories without disabling hard rules. Review rest across adjacent weeks, actual call-out work, day/night consistency, paired standby, and balanced workload. Report recurring gaps, qualified capacity, and proposed coverage improvements. Validate jurisdiction-specific policy before operational use.

## 0.09 — Scale and presentation

On-call team selector with typing completion suitable for 20–100 teams and an All teams choice. Searchable organization/team hierarchy when needed. Finish translation resources and locale-aware dates. Branding settings allow a logo and a restrained palette with preview; schedule status colors remain consistent and accessible.

## 0.10 — Delivery and external schedules

Email published schedules and subsequent changes to affected people with delivery status, acknowledgements, and failure handling; drafts never send. Export published assignments to the current Microsoft Teams Shifts Excel import template, mapping work email and scheduling group. Preview/validate rows, local date formats, 24-hour shift limit, and future-date limit before download. Shifts import adds records; it does not update or delete existing records.

## Release discipline

Use `coverage-scheduler-v0.xx.zip`, update this roadmap and `CHANGELOG.md`, build the frontend, run relevant backend checks, and keep each prior release ZIP intact. Do not treat a draft ZIP as approved until reviewed.
