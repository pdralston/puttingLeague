-- Migration: Add payout configuration columns to tournaments
ALTER TABLE tournaments ADD COLUMN buy_in_per_player DECIMAL(10,2) NOT NULL DEFAULT 5.00;
ALTER TABLE tournaments ADD COLUMN payout_config JSON NULL;
ALTER TABLE tournaments ADD COLUMN first_payout DECIMAL(10,2);
ALTER TABLE tournaments ADD COLUMN second_payout DECIMAL(10,2);

