# Coverage Scheduler — private alpha

Copy `.env.example` to `.env`, choose local secrets, and run `docker compose up --build`. Open `http://localhost:8080`; set `WEB_BIND` to the host LAN IP for access from another device. This alpha auto-enables administrator actions and must remain private.

**Coverage** defines required time periods, headcount, skills, and importance. **Schedule** holds independent employee shifts; one shift can span multiple Coverage periods. The Schedule opens on one team and remembers it; “All teams” is an explicit grouped view. The separate On-call page shows published current and upcoming names, phone numbers, times, and gaps. Teams and People have add/edit forms for recurring patterns, contact details, qualifications, availability, and preferences.

Use **Create draft** for a selected week, edit dated Coverage periods or person shifts, then **Publish**. Team weekly template edits apply to newly generated weeks; a dated draft remains independent. Recreating a draft discards its unsaved draft edits. Published shifts remain in the database until a replacement week is published. The generator uses a simple greedy heuristic with soft team and individual preferences, not an optimized multiweek rotation engine. Qualification, availability, overlap, and worked-shift rest are hard checks. Gaps remain visible.

The database now has migrations. Existing alpha volumes are upgraded with `migrate --fake-initial`: original assignment rows are copied into independent shifts once at startup. Synthetic pilot teams and people are only seeded if absent, so later edits are preserved. Back up a real database before upgrading; this remains a private alpha.

## BC scheduling checks

The pilot checks overlap and eight hours between worked shifts (BC Employment Standards Act s.36(2)). Its **employer preferences** avoid back-to-back full staffed shifts or full standby periods (eight hours each), and cap a single staffed shift at twelve hours. A twelve-hour staffed shift followed by home/mobile standby is allowed; standby is not automatically worked time. Neither the pilot preference nor twelve hours is a universal statutory cap. The roster flags the 32-hour weekly rest or premium-pay alternative (s.36(1)).

Actual call-outs, on-site standby, meal breaks, overtime/payroll, emergency exceptions, variances, collective agreements and occupational exemptions are not modelled. The application cannot certify legal compliance. Before operational use, record call-outs, assess adjacent weeks and agreements, and review the fuller `docs/scheduler-requirements.xml`. Statute: https://www.bclaws.gov.bc.ca/civix/document/id/complete/statreg/00_96113_01 .

The API and PostgreSQL remain inside Compose. Production deployment is rejected while alpha automatic admin is enabled.
