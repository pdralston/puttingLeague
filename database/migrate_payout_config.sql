-- Migration: Add payout configuration columns to tournaments
ALTER TABLE tournaments ADD COLUMN buy_in_per_player DECIMAL(10,2) NOT NULL DEFAULT 5.00;
ALTER TABLE tournaments ADD COLUMN payout_config JSON NULL;
