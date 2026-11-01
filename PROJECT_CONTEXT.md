# Project Context — DG-Putt

Quick orientation for picking this project up. For setup/API see `README.md`;
for the archive/migration plan see `docs/archive-and-migration-strategy.md`.

## What this is

DG-Putt — a disc-golf **putting league** tournament manager (double-elimination
brackets, real-time updates, season tracking). Live at
https://putt.dg-rater.com.

It is part of the broader **DG-Rater** platform but is **currently a separate
repo and EB environment**. It shares the AWS RDS MySQL instance with DG-Rater
(separate `dgputt` schema). Consolidation into the DG-Rater Flask backend is
planned (DG-Rater design doc Phase 2): fold DG-Putt in and rename its tables
`putt_*`. Not yet done.

## Current state (as of 2026-10-31)

- **Backend + frontend are both fully built and deployed to prod.** (The old
  README said the frontend was "coming soon" — that is stale; the React SPA
  exists with 20+ components and is live.)
- **Stack:** Flask + Flask-SQLAlchemy + PyMySQL + **Flask-SocketIO**
  (WebSockets for live match/bracket updates). EB platform Python 3.13 / AL2023.
- **Auth is single-axis:** `users.role` enum = `Admin` / `Director` / `Viewer`.
  (Contrast DG-Rater's two-axis org governance — DG-Putt has NOT been migrated
  to that model; it will need to be at consolidation.)
- **Schema is hand-written SQL** in `database/` (`create_tables.sql`,
  `migrate_payout_config.sql`). **No Alembic.** `create_tables.sql` is the full
  current schema (migrated end state). 10 tables (see README).
- **Season archive is IMPLEMENTED** (`backend/routes/archive.py`, Admin-only,
  with `/api/archive/preview` + `/api/archive`). It archives completed
  tournaments under a `seasons` record via `tournaments.season_id`, deletes
  incomplete tournaments, rolls `seasonal_*` → `lifetime_*` player stats, prunes
  never-active players, promotes the Am season points leader to Pro (admin
  tie-resolution via `tie_resolution`), and collapses the ace pot to one
  carry-over entry — all in a single transaction. The schema changes (the
  `seasons` table, `tournaments.season_id`, the `lifetime_*` columns, and the
  `'Pending'` tournament status) are part of `create_tables.sql` and were
  applied to prod as a one-off. The legacy `season_standings` table
  (keyed by `season_year`) is retained but no longer the archive mechanism.
  Verified against a copy of prod data; pre-archive RDS snapshot discipline in
  place. See `docs/archive-and-migration-strategy.md` for the decision record
  and as-implemented outcome.

## Layout

- `backend/app.py` — Flask app + SocketIO, config, blueprint registration.
- `backend/application.py` — EB entry point (`application = app`).
- `backend/models.py` — single-file SQLAlchemy models (10 tables).
- `backend/routes/` — auth, players, tournaments, matches, tournament_edit,
  ace_pot, admin_audit, archive.
- `frontend/` — React + TS SPA (CRA).
- `database/` — hand-written SQL schema + migrations.
- `docs/` — feature + strategy docs.

## Deployment

- EB app `DG-Putt`, env `dgputt-api` (id `e-wgcvyfa6pp`), us-west-2, profile
  `eb-deployer`. EB config at repo root, `sc: git`. `eb deploy` from repo root.
- RDS MySQL shared instance, `dgputt` schema.
- ⚠️ **Deploy gotcha (learned on the DG-Rater deploy):** keep large stray
  artifacts (installer zips, etc.) OUT of the repo dir, and make sure
  `.gitignore` excludes `node_modules`, venvs, and any big zips — with `sc: git`
  the deploy archives tracked files, but a working-dir fallback can blow the
  512MB archive limit.

## NEXT — near-term priorities

1. **Deploy the season archive to prod.** The feature is built and tested
   against a copy of prod data. The schema one-off (add `seasons`,
   `tournaments.season_id`, `lifetime_*` columns, `'Pending'` status, + payout
   backfill) has already been applied to prod RDS (pre-run snapshot
   `dgputt-db-pre-archive-20261031`). Remaining: `eb deploy` the backend, then
   smoke-test tournament creation (confirms `'Pending'`), a historical
   tournament's winners-modal payouts, and `/api/archive/preview`.
2. **Do NOT onboard DG-Putt to Alembic standalone** — defer to Phase 2
   consolidation, where its tables join DG-Rater's existing Alembic chain and
   get renamed `putt_*`. (Rationale in the strategy doc.)
3. (Optional) Promote the local-only archive test harnesses (in the gitignored
   `local/` dir) into a committed, CI-friendly test suite.

## Phase 2 — consolidation into DG-Rater (no hard deadline)

- Fold DG-Putt into the DG-Rater Flask backend; rename tables `putt_*`.
- Bring the schema under DG-Rater's single Alembic chain.
- Migrate DG-Putt's single-axis `users.role` auth onto DG-Rater's two-axis org
  governance (`org_roles` + `org_memberships`, per-org scoping).
- Fold into the org-first URL scheme `dg-rater.com/<org>/<app>`.
