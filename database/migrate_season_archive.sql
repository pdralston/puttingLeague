-- Season archive migration

-- Seasons table to track archived seasons
-- CREATE TABLE seasons (
--     season_id INT AUTO_INCREMENT PRIMARY KEY,
--     season_name VARCHAR(100) NOT NULL,
--     start_date DATE NOT NULL,
--     end_date DATE NOT NULL,
--     archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
-- );

-- Associate tournaments with a season (NULL = current season)
ALTER TABLE tournaments
    ADD COLUMN season_id INT NULL,
    ADD FOREIGN KEY (season_id) REFERENCES seasons(season_id),
    MODIFY COLUMN status ENUM('Pending', 'Scheduled', 'In_Progress', 'Completed', 'Cancelled') DEFAULT 'Scheduled';

-- Lifetime stats on players
ALTER TABLE registered_players
    ADD COLUMN lifetime_earnings DECIMAL(10,2) DEFAULT 0.00,
    ADD COLUMN lifetime_ace_pots INT DEFAULT 0,
    ADD COLUMN events_participated INT DEFAULT 0,
    ADD COLUMN seasonal_wins INT DEFAULT 0,
    ADD COLUMN average_place DECIMAL(4,2) NULL;

CREATE INDEX idx_tournament_season ON tournaments(season_id);
