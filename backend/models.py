from database import db
from datetime import datetime

class RegisteredPlayer(db.Model):
    __tablename__ = 'registered_players'
    
    player_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    player_name = db.Column(db.String(100), nullable=False)
    nickname = db.Column(db.String(50), nullable=True)
    division = db.Column(db.Enum('Pro', 'Am', 'Junior'), nullable=False)
    seasonal_points = db.Column(db.Integer, default=0)
    seasonal_cash = db.Column(db.Numeric(10, 2), default=0.00)

class TournamentRegistration(db.Model):
    __tablename__ = 'tournament_registrations'
    
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournaments.tournament_id'), primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('registered_players.player_id'), primary_key=True)
    bought_ace_pot = db.Column(db.Boolean, default=False)

class TeamHistory(db.Model):
    __tablename__ = 'team_history'
    
    player_id = db.Column(db.Integer, db.ForeignKey('registered_players.player_id'), primary_key=True)
    teammate_id = db.Column(db.Integer, db.ForeignKey('registered_players.player_id'), primary_key=True)
    times_paired = db.Column(db.Integer, default=0)
    average_place = db.Column(db.Numeric(4, 2))

class SeasonStanding(db.Model):
    __tablename__ = 'season_standings'
    
    player_id = db.Column(db.Integer, db.ForeignKey('registered_players.player_id'), primary_key=True)
    season_year = db.Column(db.Integer, primary_key=True)
    division = db.Column(db.Enum('Pro', 'Am', 'Junior'), nullable=False)
    final_place = db.Column(db.Integer)

class Tournament(db.Model):
    __tablename__ = 'tournaments'
    
    tournament_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tournament_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.Enum('Scheduled', 'In_Progress', 'Completed', 'Cancelled'), default='Scheduled')
    total_teams = db.Column(db.Integer)
    ace_pot_payout = db.Column(db.Numeric(10, 2), default=0.00)

class AcePot(db.Model):
    __tablename__ = 'ace_pot'
    
    ace_pot_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournaments.tournament_id'), nullable=True)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)

class Team(db.Model):
    __tablename__ = 'teams'
    
    team_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournaments.tournament_id'), nullable=False)
    player1_id = db.Column(db.Integer, db.ForeignKey('registered_players.player_id'), nullable=False)
    player2_id = db.Column(db.Integer, db.ForeignKey('registered_players.player_id'), nullable=True)
    is_ghost_team = db.Column(db.Boolean, default=False)
    seed_number = db.Column(db.Integer)
    final_place = db.Column(db.Integer)

class Match(db.Model):
    __tablename__ = 'matches'
    
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournaments.tournament_id'), primary_key=True)
    match_id = db.Column(db.Integer, primary_key=True)
    stage_type = db.Column(db.Enum('Group_A', 'Group_B', 'Finals'), nullable=False)
    round_type = db.Column(db.Enum('Winners', 'Losers', 'Championship'), nullable=False)
    stage_match_number = db.Column(db.Integer, nullable=False)
    match_order = db.Column(db.Integer, nullable=False)
    team1_id = db.Column(db.Integer, db.ForeignKey('teams.team_id'), nullable=True)
    team2_id = db.Column(db.Integer, db.ForeignKey('teams.team_id'), nullable=True)
    team1_score = db.Column(db.Integer)
    team2_score = db.Column(db.Integer)
    station_assignment = db.Column(db.Integer)
    match_status = db.Column(db.Enum('Scheduled', 'In_Progress', 'Completed', 'Pending'), default='Pending')
    winner_advances_to_match_id = db.Column(db.Integer, db.ForeignKey('matches.match_id'), nullable=True)
    loser_advances_to_match_id = db.Column(db.Integer, db.ForeignKey('matches.match_id'), nullable=True)
