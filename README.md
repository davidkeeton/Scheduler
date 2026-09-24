# Coverage Scheduler — version 0.04.1 (private alpha)

Copy `.env.example` to `.env`, choose local secrets, and run `docker compose up --build`. The web port binds to `0.0.0.0:8080` by default; open `http://<server-IP>:8080` from another device. Keep the alpha app behind your LAN/firewall while automatic administrator actions are enabled.

**Coverage** defines required time periods, headcount, skills, and importance. **Schedule** holds independent employee shifts; one shift can span multiple Coverage periods. The Schedule opens on one team and remembers it; “All teams” is an explicit grouped view. The separate On-call page shows published current and upcoming names, phone numbers, times, and gaps. Teams and People have add/edit forms for recurring patterns, contact details, qualifications, availability, and preferences.

Use **Create draft** for a selected week, edit dated Coverage periods or person shifts, then **Publish**. Team weekly template edits apply to newly generated weeks; a dated draft remains independent. Recreating a draft discards its unsaved draft edits. Published shifts remain in the database until a replacement week is published. The generator uses a simple greedy heuristic with soft team and individual preferences, not an optimized multiweek rotation engine. Qualification, availability, overlap, and worked-shift rest are hard checks. Gaps remain visible.

The database now has migrations. Existing alpha volumes are upgraded with `migrate --fake-initial`: original assignment rows are copied into independent shifts once at startup. Synthetic pilot teams and people are only seeded if absent, so later edits are preserved. Back up a real database before upgrading; this remains a private alpha.

## BC scheduling checks

The pilot checks overlap and eight hours between worked shifts (BC Employment Standards Act s.36(2)). Its **employer preferences** avoid back-to-back full staffed shifts or full standby periods (eight hours each), and cap a single staffed shift at twelve hours. A twelve-hour staffed shift followed by home/mobile standby is allowed; standby is not automatically worked time. Neither the pilot preference nor twelve hours is a universal statutory cap. The roster flags the 32-hour weekly rest or premium-pay alternative (s.36(1)).

Actual call-outs, on-site standby, meal breaks, overtime/payroll, emergency exceptions, variances, collective agreements and occupational exemptions are not modelled. The application cannot certify legal compliance. Before operational use, record call-outs, assess adjacent weeks and agreements, and review the fuller `docs/scheduler-requirements.xml`. Statute: https://www.bclaws.gov.bc.ca/civix/document/id/complete/statreg/00_96113_01 .

The API and PostgreSQL remain inside Compose. Production deployment is rejected while alpha automatic admin is enabled.

## Version 0.04.1

Use **Copy week…** on Schedule or Coverage to carry a prior draft or published week forward into the selected week. Preview shows counts and assignment conflicts. The copy creates a draft for all teams, preserving employee assignments, Coverage requirements, role, location, notes and break duration at the same local times; elapsed time can change across a daylight-saving transition. An existing target draft requires explicit replacement. Review conflicts and the copied draft before publishing. Reset draft asks for confirmation.

## Version 0.04

Week navigation, publication snapshots and revision comparison, time off/sick call and actual standby call-out records, editable role/location/break/notes on shifts, basic event history, and backup/restore instructions. Newly recorded absences block conflicting publication; actual call-out work raises rest advisories and blocks conflicting worked shifts on publication. Existing published weeks from before 0.04 are browsable, but have no historical revision snapshots. See `docs/backup-restore.md`.

The alpha still uses automatic administrator access behind a private LAN boundary. Individual access control and employee self-service are scheduled for 0.07. The event actor is therefore the generic alpha administrator; it cannot identify a person until accounts exist. Break minutes are informational and do not reduce calculated coverage until exact break windows are modelled. Actual call-outs do not calculate payroll or certify legal compliance.

## Version 0.03

The Teams page now shows all teams in one edit list without redundant team or week filters.

## Version 0.02

The On-call contact list includes staffed and standby shifts in chronological vertical order, with handoff details and missing phone indicators. Casual staff can maintain positive availability on a person calendar and preview .ics imports (duplicates and unavailable-time conflicts) before applying. Export writes dated availability events. The import accepts dated VEVENT periods; recurring rules are rejected with an explanation. English Canadian text and formatting are centralized for the new contact view; broader interface translation remains future work.

Version labels use 0.02 for the release; the frontend package uses semantic version 0.0.2. The database migration adds `available_windows` to Employee.

See `ROADMAP.md` for the versioned feature plan.

## Next work (after 0.02)

- Dedicated Skills section to manage qualifications, person assignments, and Coverage requirements.

- Employee registration and account management, with role-bound self-service availability editing.
- Email delivery of published schedules and changes, with delivery status.
- Microsoft Teams Shifts Excel export from published assignments; map work email and scheduling group, validate the template and preview the workbook before download. Teams import adds entries rather than updating existing ones.
