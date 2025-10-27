# DG Putt

Disc golf putting league tournament management system with automated bracket generation and season tracking.

## Features

- Event registration with ace pot tracking
- Automated team building and seeding
- Double elimination tournament brackets
- Season standings and leaderboards
- Multi-role authentication system

## Setup

### Prerequisites
- Python 3.8+
- MySQL 8.0+
- Node.js 16+ (for frontend)

### Backend Setup
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your database credentials
python app.py
```

### Database Setup
```bash
docker exec -i <mysql_container_name> mysql -u root -p your_database < database/create_tables.sql
```

## Project Structure

- `backend/` - Flask API server
- `frontend/` - React application (coming soon)
- `database/` - SQL schema and migrations
- `docs/` - Technical documentation
