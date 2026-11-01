# DG-Putt — Season Archive & Migration Strategy (decision note)

_Recorded 2026-10-22. Context: next season starts in ~1.5 weeks; a season-archive
branch exists but is UNPUSHED on the desktop (reachable in a few days)._

> **STATUS UPDATE (2026-10-31): IMPLEMENTED.** The desktop branch was pushed and
> the archive feature is finished, tested against a copy of prod data, and
> committed. The decision record below is preserved as history; see
> **"As-implemented outcome"** at the end for how the open questions resolved.

## TL;DR decisions

1. **Finish the season-archive feature using DG-Putt's CURRENT `.sql`-migration
   style now** (before the season boundary). Do NOT stand up Alembic just for
   this one migration under deadline pressure.
2. **Defer Alembic onboarding for DG-Putt to Phase 2** (the DG-Rater
   consolidation), when DG-Putt's tables move under the DG-Rater backend's
   EXISTING Alembic chain and get renamed `putt_*`.
3. **Wait for the desktop archive branch** rather than redoing the work blind.
   The other three tasks (consolidation prep, DG-Rater routing, DG-Tags
   frontend) are not truly blocked — they can proceed in parallel during the
   wait. A few days' wait + ~half a day to finish still fits inside the 1.5-week
   runway.

## Why wait for the desktop branch

- Redoing from scratch is ~half a day, but the crux is a **schema decision**
  (see below) that the desktop branch may already have solved. Committing to a
  schema/migration strategy twice — then reconciling two designs against a live
  prod schema on a deadline — is the expensive failure mode.
- Cheapest path: push the branch from the desktop (~5 min) and read the diff
  before writing anything. Even just for reference.

## Why NOT onboard DG-Putt to Alembic now

- DG-Putt currently manages schema with hand-written `.sql` files in
  `database/` (`create_tables.sql`, `migrate_payout_config.sql`). No ordered
  chain, no current-revision concept, no downgrade path.
- **Phase 2 renames DG-Putt tables to `putt_*`** and moves the code under the
  DG-Rater backend, which ALREADY has Alembic configured (`migrations/`, prod
  head `c3d4e5f6a7b8`). Building a standalone Alembic baseline now — against the
  current table names — would be thrown away at consolidation. Doing it twice.
- Standing up `alembic.ini` + `env.py` + stamping a baseline against the prod
  schema, then testing it, is risk-adding under a deadline. For a single
  additive archive migration, a hand-written `.sql` in the existing style is the
  lower-risk bridge.
- Correct sequence: at consolidation, fold DG-Putt's tables into DG-Rater's
  SINGLE Alembic chain in the same migration that renames them `putt_*`. That is
  the end-state and where the "DG-Dubs does it cleanly" lesson actually pays off.
- Reconsider only if DG-Putt's schema will churn heavily BEFORE consolidation
  (multiple migrations in the coming weeks). For one archive migration, it won't.

## Key schema finding (the crux the archive work must resolve)

The DG-Dubs archive (`backend/apps/dubs/routes/archive.py`) hinges on
`Tournament.season_id` (filter `season_id=None`, then stamp it). **DG-Putt's
`Tournament` model has no `season_id` column.** DG-Putt instead has a
`season_standings` table keyed by `season_year`, implying a **year-based**
archival model, not the DG-Dubs `season_id`-FK model.

So the DG-Putt archive needs a schema decision + migration: either add
`season_id`/`season_year` to `tournaments`, or snapshot final results into
`season_standings`. **Check whether the desktop branch already answers this
before designing a new approach.**

## How DG-Putt differs from DG-Dubs (don't copy-paste the archive)

DG-Dubs is Elo-rated doubles; DG-Putt is points/placement-based. Steps that do
NOT map from the DG-Dubs archive:

- **No `rating` on DG-Putt players** → drop the rating-normalization step
  (DG-Dubs normalizes into a 900–1400 band).
- **No `lifetime_*` columns** on `RegisteredPlayer` (only `seasonal_points` /
  `seasonal_cash`) → there is no "roll seasonal → lifetime"; instead reset
  seasonal points/cash and likely snapshot final standings into
  `season_standings`.
- **Ace pot shape differs:** DG-Dubs uses `ace_pot_tracker` (with a running
  `balance`); DG-Putt has an `ace_pot` table with no running balance column →
  carry-over logic must be rewritten, not ported.
- **No in-memory rating system** to reload in DG-Putt → drop that step.

## Lessons from DG-Dubs to CARRY INTO the DG-Putt archive

- **Add a `preview` / dry-run endpoint** before the destructive archive
  (DG-Dubs has `/api/archive/preview`). Valuable for a once-a-season
  irreversible operation.
- **Wrap the whole archive in ONE transaction** with `try / commit / except
  rollback` (as DG-Dubs does) so a partial archive can't corrupt the season
  boundary.
- **Take a prod DB snapshot immediately before running it** (same discipline as
  the `dgputt-db-pre-s13-20260109` snapshot from the §13 migration).
  Non-negotiable for a once-a-year irreversible operation.

## Rough effort to redo (if the desktop branch turns out unusable)

~half a day total: schema decision + hand-written migration (~1–2h, the risk),
port the archive endpoint to DG-Putt semantics (~2–3h), frontend trigger +
verify on a DB copy + deploy (~1–2h).

## Next actions

1. Reach the desktop; push the archive branch (or confirm it's unrecoverable).
2. Read the diff — specifically how it resolves the `season_id` vs
   `season_year` schema question.
3. Finish/deploy the archive well before the season boundary; snapshot prod
   first; verify on a copy.
4. (Parallel, no deadline) proceed on consolidation prep / routing / DG-Tags
   frontend.
5. (Phase 2) onboard DG-Putt schema into DG-Rater's Alembic chain at
   consolidation, renaming tables `putt_*`.

---

## As-implemented outcome (2026-10-31)

The desktop branch was pushed and reviewed. How the open questions resolved:

- **Schema crux (`season_id` vs `season_year`): resolved in favor of the
  `season_id`-FK model** (same shape as DG-Dubs). The schema gained a `seasons`
  table, `tournaments.season_id` (NULL = current season, FK to `seasons`), the
  `lifetime_*` columns on `registered_players`, and a `'Pending'` value on
  `tournaments.status`. These are now part of `create_tables.sql` (the
  fresh-install schema) and were applied to the existing prod DB as a one-off.
  The legacy `season_standings` table (keyed by `season_year`) is **retained but
  no longer the archive mechanism** — nothing writes to it now.
- **Migration style:** kept to the hand-written `.sql` approach as decided; no
  standalone Alembic. (Phase 2 consolidation decision unchanged.)
- **DG-Dubs lessons carried over:** `/api/archive/preview` dry-run endpoint ✓;
  whole archive wrapped in one `try / commit / except rollback` transaction ✓;
  pre-archive RDS snapshot taken (`dgputt-db-pre-archive-20261031`) ✓.
- **DG-Putt-specific semantics (not ported from DG-Dubs):** no rating
  normalization; ace-pot carry-over rewritten for the balance-less `ace_pot`
  table; only **Completed** tournaments are archived; incomplete tournaments are
  **deleted** at archive time; never-active players (no team row in any season)
  are pruned — players with prior-season history are retained; Am→Pro promotion
  applies only to the Am **seasonal_points leader**, with a `409` tie-prompt and
  `tie_resolution` admin selection when multiple players tie.

### Verification performed

- Migration applied cleanly to a prod-shaped schema and to a copy of **real
  prod data** (164 players, 20 completed tournaments).
- Archive dry-run against real-data copy behaved as expected (102 stale
  seed-import players pruned, single clear Am leader promoted, $40 ace-pot
  carry-over).
- Integration + edge-case tests pass (empty-season guard, Completed-only
  tagging, incomplete deletion, full Am-tie resolution flow, prior-season player
  retention). Harnesses live in the gitignored `local/` dir.
- Frontend tie-resolution flow manually E2E-tested end to end.

### Remaining before the feature is live

- **Schema one-off applied to prod** (added `seasons`, `tournaments.season_id`,
  `lifetime_*` columns, `'Pending'` status, + historical payout backfill) ahead
  of the code deploy, since the backend writes `status='Pending'` which must
  exist first. Pre-run snapshot `dgputt-db-pre-archive-20261031` is the rollback
  anchor. Remaining: `eb deploy` the backend, then smoke-test.

### Correction to the original note

The original "Key schema finding" said DG-Putt had **no `lifetime_*` columns**
and would "likely snapshot final standings into `season_standings`." That path
was **not** taken: the implementation **adds** `lifetime_*` columns and rolls
seasonal → lifetime, and does not use `season_standings`.
