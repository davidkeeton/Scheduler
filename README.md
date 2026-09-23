# Coverage Scheduler — first runnable slice

Copy `.env.example` to `.env`, choose local secrets, then run `docker compose up --build`. Open `http://localhost:8080`. To use another device on your home network, set `WEB_BIND` in `.env` to the Docker host's LAN IP and open `http://<that-IP>:8080`.

This private alpha seeds the synthetic 8-person and 20-person teams after a database reset. It opens with master-admin capabilities automatically. Do not expose the alpha deployment publicly. To reset the pilot database, run `docker compose down -v` and start it again.

The first slice generates one week of draft shifts, shows gaps and cross-team assignments, lets a manager move assignments between eligible people, publishes a roster, and looks up current on-call coverage. Help/About contains the product specification summary and links to `docs/scheduler-requirements.xml`.

Pilot defaults are illustrative: one qualified person per coverage interval; Team 1 staffed 11:00–19:00 weekdays and on call otherwise; Team 2 staffed around the clock. Team 1 hours and Eastern-time priority examples still need confirmation. The generator uses a deterministic greedy heuristic in this slice; OR-Tools, full rule configuration, vacation approval, notification delivery, and Teams export remain later implementation work.

Only the web port is published. The API and PostgreSQL stay inside Compose. This alpha configuration is deliberately refused if `APP_ENV=production` and `ALPHA_AUTO_ADMIN=1`.
