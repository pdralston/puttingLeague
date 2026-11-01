# DG-Putt

Disc golf putting league tournament management system with automated
double-elimination bracket generation, real-time match updates, and season
tracking.

**Live:** https://putt.dg-rater.com

> **Note:** DG-Putt is currently a standalone project/repo with its own
> Elastic Beanstalk environment, but it shares the AWS RDS MySQL instance with
> DG-Rater (separate `dgputt` schema). Consolidation into the DG-Rater backend
> is planned (tables to be renamed `putt_*`). See
> `docs/archive-and-migration-strategy.md`.

## Architecture

- **Backend** — Flask + Flask-SQLAlchemy + PyMySQL + Flask-SocketIO
  (WebSockets for live match/bracket updates). App object in `backend/app.py`,
  EB entry point `backend/application.py`.
- **Frontend** — React + TypeScript (Create React App) in `frontend/`.
- **Database** — MySQL 8.0 (AWS RDS, shared instance; `dgputt` schema).
  Schema managed by hand-written SQL in `database/` (not Alembic — see the
  migration strategy note).
- **Auth** — Session-based (Werkzeug password hashing). Three roles:
  `Admin` / `Director` / `Viewer` (single-axis `users.role` enum).

## Features

- Player registry with divisions (Pro / Am / Junior), nicknames, CSV bulk import
- Event registration with ace-pot opt-in tracking
- Automated team building and seeding
- **Double-elimination tournament brackets** (Group A / Group B / Finals)
- **Real-time updates via WebSockets** (clients join per-tournament rooms)
- Seasonal points and cash payout tracking per player
- Season standings / leaderboards
- **Season archive** — end-of-season rollover: archives completed tournaments
  under a `Season` record, deletes incomplete tournaments, rolls seasonal →
  lifetime stats, prunes never-active players, promotes the Am-division season
  points leader to Pro (with admin tie-resolution), and collapses the ace pot
  to a single carry-over entry. Includes a preview/dry-run endpoint and runs in
  a single transaction. See `docs/archive-and-migration-strategy.md`.
- **Tournament editing** for in-progress tournaments (team assignments, match
  progression, adding matches) — see `docs/tournament-edit.md`
- **Admin audit & recalculation** — manual final-place overrides with
  dependent-stat recalculation that preserves overrides
- Multi-role authentication with user management (Admin-only create/delete)

## Project Structure

```
puttingLeague/
├── backend/
│   ├── app.py                 # Flask app factory + SocketIO setup, blueprint registration
│   ├── application.py         # EB entry point (exposes `application`)
│   ├── database.py            # SQLAlchemy() instance
│   ├── models.py              # 10 models: User, Season, RegisteredPlayer,
│   │                          #   TournamentRegistration, Team, Match, TeamHistory,
│   │                          #   SeasonStanding, AcePot, Tournament
│   ├── routes/
│   │   ├── auth.py            # Login/logout/me, user CRUD, reset-data
│   │   ├── players.py         # Player CRUD + CSV import + detail/history
│   │   ├── tournaments.py     # Tournament lifecycle
│   │   ├── matches.py         # Match scoring, bracket progression, payouts
│   │   ├── tournament_edit.py # In-progress tournament editing
│   │   ├── ace_pot.py         # Ace-pot entries (read)
│   │   ├── admin_audit.py     # Audit view + manual place override + recalc
│   │   └── archive.py         # Season archive: preview + perform (Admin only)
│   ├── .ebextensions/         # EB platform config (packages, nginx, env)
│   └── requirements.txt
├── frontend/                  # React + TS SPA (CRA)
│   └── src/components/        # Login, Admin, TournamentCreation,
│                              #   UnifiedTournamentView, BracketView, Match,
│                              #   Leaderboard, PlayerManager, AcePotTracker,
│                              #   AdminAudit, TournamentEdit, etc.
├── database/
│   ├── create_tables.sql      # Full schema for fresh installs (migrated end state)
│   └── migrate_payout_config.sql
└── docs/
    ├── tournament-edit.md
    └── archive-and-migration-strategy.md
```

## Getting Started

### Prerequisites

- Python 3.13 (prod EB platform; 3.8+ likely works locally)
- Node.js 16+
- MySQL 8.0+

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env     # edit DB credentials
python app.py            # runs via SocketIO on http://localhost:5000
```

### Database (fresh install)

```bash
docker exec -i <mysql_container> mysql -u root -p dgputt < database/create_tables.sql
```

> `create_tables.sql` is the full, current schema — it already includes the
> `seasons` table, `tournaments.season_id`, the `'Pending'` status, and the
> `lifetime_*` player columns. A fresh install needs nothing further.

### Frontend

```bash
cd frontend
npm install
npm start                # http://localhost:3000
```

## Data Model (10 tables)

| Table | Purpose |
|-------|---------|
| `users` | Auth; role enum Admin/Director/Viewer |
| `seasons` | Archived-season records; name, start/end dates, archived-at |
| `registered_players` | Player registry; `seasonal_*` + `lifetime_*` stats, division |
| `tournaments` | Events; status, payout config, ace-pot payout, `season_id` (NULL = current) |
| `tournament_registrations` | Player↔tournament, ace-pot opt-in |
| `teams` | Team compositions; seed, final place, points earned |
| `matches` | Double-elim matches; stage/round, scores, advancement pointers |
| `team_history` | Teammate pairing stats (times paired, avg place) |
| `season_standings` | Legacy historical standings table, keyed by `(player_id, season_year)`; not written by the current archive (which uses `seasons` + `season_id`) |
| `ace_pot` | Ace-pot transaction history |

> **Season archive (implemented):** archiving stamps completed tournaments with
> a `season_id` pointing at a `seasons` record, rolls `seasonal_*` → `lifetime_*`
> player stats, and resets seasonal stats. `tournaments.status` includes a
> `'Pending'` value and `tournaments.season_id` exists. The older
> `season_standings` table is retained but no longer the archive mechanism. See
> `docs/archive-and-migration-strategy.md`.

## Deployment

- **Backend:** AWS Elastic Beanstalk — app `DG-Putt`, env `dgputt-api`
  (us-west-2), Python 3.13 / Amazon Linux 2023. EB config at repo root
  (`.elasticbeanstalk/`), `sc: git`, profile `eb-deployer`.
- **Database:** AWS RDS MySQL (shared instance, `dgputt` schema).

Deploy backend (from repo root, on a machine with the `eb-deployer` profile and
EB config):
```bash
eb deploy --profile eb-deployer
```

## Documentation

- `docs/tournament-edit.md` — tournament editing feature + API
- `docs/archive-and-migration-strategy.md` — season-archive + Alembic/
  consolidation decisions
