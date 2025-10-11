-- DG Putt Database Schema
-- SQL DDL for creating all tables

-- Main player registry
CREATE TABLE registered_players (
    player_id INT AUTO_INCREMENT PRIMARY KEY,
    player_name VARCHAR(100) NOT NULL,
    nickname VARCHAR(50) NULL,
    division ENUM('Pro', 'Am', 'Junior') NOT NULL,
    seasonal_points INT DEFAULT 0,
    seasonal_cash DECIMAL(10,2) DEFAULT 0.00
);

-- Tournament player registrations with ace pot tracking
CREATE TABLE tournament_registrations (
    tournament_id INT NOT NULL,
    player_id INT NOT NULL,
    bought_ace_pot BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (tournament_id, player_id),
    FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id),
    FOREIGN KEY (player_id) REFERENCES registered_players(player_id)
);

-- Player team pairing statistics
CREATE TABLE team_history (
    player_id INT,
    teammate_id INT,
    times_paired INT DEFAULT 0,
    average_place DECIMAL(4,2),
    PRIMARY KEY (player_id, teammate_id),
    FOREIGN KEY (player_id) REFERENCES registered_players(player_id),
    FOREIGN KEY (teammate_id) REFERENCES registered_players(player_id)
);

-- Historical season standings
CREATE TABLE season_standings (
    player_id INT,
    season_year INT,
    division ENUM('Pro', 'Am', 'Junior') NOT NULL,
    final_place INT,
    PRIMARY KEY (player_id, season_year),
    FOREIGN KEY (player_id) REFERENCES registered_players(player_id),
    CHECK (final_place > 0)
);

-- Tournament records
CREATE TABLE tournaments (
    tournament_id INT AUTO_INCREMENT PRIMARY KEY,
    tournament_date DATE NOT NULL,
    status ENUM('Scheduled', 'In_Progress', 'Completed', 'Cancelled') DEFAULT 'Scheduled',
    total_teams INT,
    ace_pot_payout DECIMAL(10,2) DEFAULT 0.00
);

-- Ace pot transaction history
CREATE TABLE ace_pot (
    ace_pot_id INT AUTO_INCREMENT PRIMARY KEY,
    tournament_id INT NULL,
    date DATE NOT NULL,
    description VARCHAR(255) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id),
    CHECK (amount != 0)
);

-- Team compositions for tournaments
CREATE TABLE teams (
    team_id INT AUTO_INCREMENT PRIMARY KEY,
    tournament_id INT NOT NULL,
    player1_id INT NOT NULL,
    player2_id INT NULL,
    is_ghost_team BOOLEAN DEFAULT FALSE,
    seed_number INT,
    final_place INT NULL,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id),
    FOREIGN KEY (player1_id) REFERENCES registered_players(player_id),
    FOREIGN KEY (player2_id) REFERENCES registered_players(player_id),
    CHECK (seed_number > 0),
    CHECK (final_place > 0 OR final_place IS NULL)
);

-- Individual match records
CREATE TABLE matches (
    match_id INT AUTO_INCREMENT PRIMARY KEY,
    tournament_id INT NOT NULL,
    stage_type ENUM('Group_A', 'Group_B', 'Finals') NOT NULL,
    round_type ENUM('Winners', 'Losers', 'Championship') NOT NULL,
    stage_match_number INT NOT NULL,
    global_match_order INT NOT NULL,
    team1_id INT NOT NULL,
    team2_id INT NOT NULL,
    team1_score INT NULL,
    team2_score INT NULL,
    station_assignment INT,
    match_status ENUM('Scheduled', 'In_Progress', 'Completed') DEFAULT 'Scheduled',
    FOREIGN KEY (tournament_id) REFERENCES tournaments(tournament_id),
    FOREIGN KEY (team1_id) REFERENCES teams(team_id),
    FOREIGN KEY (team2_id) REFERENCES teams(team_id),
    CHECK (stage_match_number > 0),
    CHECK (global_match_order > 0),
    CHECK (team1_score >= 0 OR team1_score IS NULL),
    CHECK (team2_score >= 0 OR team2_score IS NULL),
    CHECK (station_assignment BETWEEN 1 AND 6)
);

-- Performance indexes
CREATE INDEX idx_player_name ON registered_players(player_name);
CREATE INDEX idx_tournament_date ON tournaments(tournament_date);
CREATE INDEX idx_season_year ON season_standings(season_year);
CREATE INDEX idx_match_tournament ON matches(tournament_id, global_match_order);
CREATE INDEX idx_team_tournament ON teams(tournament_id);
