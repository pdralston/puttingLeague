# Tech Design Template

## Project Overview
**Project Name:** DG Putt

**Brief Description:**

Featuring an automated mulit-stage double elimination tournament bracket manager as well as a season standings leaderboard and robust event registration workflow, DG Putt has all you need to host a great event

**Problem Statement:** Prior to DG Putt, a combination of excel spreadsheets, manual data entry, a 3rd party tournament bracket application, and specialized html pages with tampermonkey scripts had to be used to run an event. This made it unscalable and unapproachable for non-tech saavy admins to facilitate the event. DG Rater aims to solve this problem with a robust feature set presented by an intuitive UI.

## Core Requirements

### Functional Requirements
- An event registration system that allows selecting from previously registered players, adding a new player, remarking if they bought in to the ace pot for the current event
- A persistant player record database table that maintains the player's name, current season points, and division (Pro, Am, or Junior)
- A persistant Ace Pot database table that maintains a running total of the Ace
- A persistant Tournament database table that maintains records of past events including completed bracket and overall standings
- An automated team builder that will randomly generate teams of two players and seed those teams into the tournament bracket
- An automated tournament bracket manager that supports group and final stages, double elimination format, station assignment and a beautiful UI that depicts the bracket as a whole and highlights the current matches and allows for entering match results to advance the tournament
- A divisional leaderboard that showcases the players and their standing for the current season. Season points are earned for each event attended (1 point), each game of a tournament won (1 point), and by going undefeated in a night (3 points)

### Non-Functional Requirements
- **Performance:**
  - Most operations are iterative in nature with expected performance approaching O(1) with the most complicated operations being no more than O(n)
- **Scalability:**
  - Expected load is small with minimal scaling needed
- **Availability:**
  - As needed availability with low TPS expected
- **Security:**
  - CRUD operations must be protected behind a login system with Admins having full CRUD permissions, Tournament Directors having CRU permissions and unauthenticated users only being able to view the Divisional leaderboard, current and previous tournament brackets, and the Ace Pot tracker

## User Stories
**Primary User:** The tournament directors are the primary users followed by unauthenticated observers that may check on current tournament progress or previous tournament statistics.

## Technical Architecture

### System Components
- **Frontend:** React 
- **Backend:** Python
- **Database:** SQL
- **External APIs:** Potentially

## Database Structures

### Registered_Players
- **PRIMARY KEY:** Player_ID
- Player_ID
  - Type: INT (AUTO_INCREMENT)
  - Description: Unique identifier for each player
- Player_Name
  - Type: VARCHAR(100)
  - Description: Player's full name
- Nickname
  - Type: VARCHAR(50) NULLABLE
  - Description: An optional name for display in the tournament bracket during events
- Division
  - Type: ENUM('Pro', 'Am', 'Junior')
  - Description: Current season division. Players who win AM get bumped to Pro. Juniors must be under 18.
- Seasonal_Points
  - Type: INT
  - Description: Current season point total. 1 point per event, 1 per match win, 2 for final 4, 3 for undefeated.
- Seasonal_Cash
  - Type: DECIMAL(10,2)
  - Description: Running total of cash payouts earned this season. Split equally unless ghost player involved.

### Team_History
- **PRIMARY KEY:** (Player_ID, Teammate_ID)
- Player_ID
  - Type: INT (FOREIGN KEY → Registered_Players.Player_ID)
  - Description: Reference to player
- Teammate_ID
  - Type: INT (FOREIGN KEY → Registered_Players.Player_ID)
  - Description: Reference to teammate
- Times_Paired
  - Type: INT
  - Description: Number of times this pairing has occurred in current season
- Average_Place
  - Type: DECIMAL(4,2)
  - Description: Average tournament placement for this pairing

### Season_Standings
- **PRIMARY KEY:** (Player_ID, Season_Year)
- Player_ID
  - Type: INT (FOREIGN KEY → Registered_Players.Player_ID)
  - Description: Reference to player
- Season_Year
  - Type: INT
  - Description: 4-digit year (e.g., 2024)
- Division
  - Type: ENUM('Pro', 'Am', 'Junior')
  - Description: Division played in that season
- Final_Place
  - Type: INT
  - Description: Overall season ranking achieved

### Ace_Pot
- **PRIMARY KEY:** Ace_Pot_ID
- Ace_Pot_ID
  - Type: INT (AUTO_INCREMENT)
  - Description: Unique identifier for each ace pot transaction
- Tournament_ID
  - Type: INT (FOREIGN KEY → Tournaments.Tournament_ID, NULL allowed)
  - Description: Tournament associated with this transaction (NULL for general buy-ins)
- Date
  - Type: DATE
  - Description: Date when ace pot balance was modified
- Description
  - Type: VARCHAR(255)
  - Description: Reason for balance change (player buy-in, undefeated payout, etc.)
- Amount
  - Type: DECIMAL(10,2)
  - Description: Dollar amount change (positive for buy-ins, negative for payouts)
  - Constraint: CHECK (Amount != 0)

### Tournaments
- **PRIMARY KEY:** Tournament_ID
- Tournament_ID
  - Type: INT (AUTO_INCREMENT)
  - Description: Unique identifier for each tournament
- Tournament_Date
  - Type: DATE
  - Description: Date tournament was held
- Status
  - Type: ENUM('Scheduled', 'In_Progress', 'Completed', 'Cancelled')
  - Description: Current tournament status
- Total_Teams
  - Type: INT
  - Description: Number of teams that participated
- Ace_Pot_Payout
  - Type: DECIMAL(10,2)
  - Description: Amount paid out from ace pot (if any team went undefeated)

### Teams
- **PRIMARY KEY:** Team_ID
- Team_ID
  - Type: INT (AUTO_INCREMENT)
  - Description: Unique identifier for each team
- Tournament_ID
  - Type: INT (FOREIGN KEY → Tournaments.Tournament_ID)
  - Description: Tournament this team participated in
- Player1_ID
  - Type: INT (FOREIGN KEY → Registered_Players.Player_ID)
  - Description: First team member
- Player2_ID
  - Type: INT (FOREIGN KEY → Registered_Players.Player_ID, NULL allowed)
  - Description: Second team member (NULL for ghost player)
- Is_Ghost_Team
  - Type: BOOLEAN
  - Description: True if this team has a ghost player (Player2_ID is NULL)
- Seed_Number
  - Type: INT
  - Description: Team's seeding position in tournament
  - Constraint: CHECK (Seed_Number > 0)
- Final_Place
  - Type: INT
  - Description: Final tournament placement (NULL if tournament incomplete)
  - Constraint: CHECK (Final_Place > 0 OR Final_Place IS NULL)

### Matches
- **PRIMARY KEY:** Match_ID
- Match_ID
  - Type: INT (AUTO_INCREMENT)
  - Description: Unique identifier for each match
- Tournament_ID
  - Type: INT (FOREIGN KEY → Tournaments.Tournament_ID)
  - Description: Tournament this match belongs to
- Stage_Type
  - Type: ENUM('Group_A', 'Group_B', 'Finals')
  - Description: Which bracket stage this match is in
- Round_Type
  - Type: ENUM('Winners', 'Losers', 'Championship')
  - Description: Winners bracket, losers bracket, or championship match
- Stage_Match_Number
  - Type: INT
  - Description: Match number within the specific stage/bracket
  - Constraint: CHECK (Stage_Match_Number > 0)
- Global_Match_Order
  - Type: INT
  - Description: Chronological order across entire tournament
  - Constraint: CHECK (Global_Match_Order > 0)
- Team1_ID
  - Type: INT (FOREIGN KEY → Teams.Team_ID)
  - Description: First team in match
- Team2_ID
  - Type: INT (FOREIGN KEY → Teams.Team_ID)
  - Description: Second team in match
- Team1_Score
  - Type: INT
  - Description: Score achieved by Team1 (NULL if match not played)
  - Constraint: CHECK (Team1_Score >= 0 OR Team1_Score IS NULL)
- Team2_Score
  - Type: INT
  - Description: Score achieved by Team2 (NULL if match not played)
  - Constraint: CHECK (Team2_Score >= 0 OR Team2_Score IS NULL)
- Station_Assignment
  - Type: INT
  - Description: Physical station/location where match is played
  - Constraint: CHECK (Station_Assignment BETWEEN 1 AND 6)
- Match_Status
  - Type: ENUM('Scheduled', 'In_Progress', 'Completed')
  - Description: Current status of this match

## Key Relationships

- **Players** can have multiple **Team_History** records (one per teammate)
- **Players** can have multiple **Season_Standings** records (one per season)
- **Tournaments** contain multiple **Teams**
- **Teams** participate in multiple **Matches**
- **Matches** belong to one **Tournament** and reference two **Teams**
- **Ace_Pot** tracks all balance changes over time, optionally linked to tournaments

## Indexes for Performance

```sql
-- Business field indexes for common queries
CREATE INDEX idx_player_name ON Registered_Players(Player_Name);
CREATE INDEX idx_tournament_date ON Tournaments(Tournament_Date);
CREATE INDEX idx_season_year ON Season_Standings(Season_Year);
CREATE INDEX idx_match_tournament ON Matches(Tournament_ID, Global_Match_Order);
CREATE INDEX idx_team_tournament ON Teams(Tournament_ID);
```

## Check Constraints

- Ace_Pot.Amount cannot be zero
- Seed_Number and Final_Place must be positive
- Scores must be non-negative
- Station_Assignment must be between 1 and 6 (configurable range)
- Match numbering must be positive

## Notes

- Ghost players: Player2_ID can be NULL in Teams table, Is_Ghost_Team flag for easy identification
- Undefeated teams: Trigger ace pot payout and reset balance to 0
- Double elimination: Handled through Stage_Type and Round_Type (Winners/Losers brackets)
- Station assignment: Physical putting stations for match organization
- Tournament linkage: Ace pot transactions can be linked to specific tournaments
