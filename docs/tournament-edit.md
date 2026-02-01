# Tournament Edit Feature

## Overview

The Tournament Edit feature allows administrators and directors to modify in-progress tournaments. This includes editing team assignments, adding new matches, and modifying match progression paths.

## Access

- **Admin users**: Full access to all tournament edit features
- **Director users**: Full access to all tournament edit features  
- **Viewer users**: No access to tournament editing

## Features

### 1. Edit Match Teams

Allows modification of team assignments for any match in the tournament.

- Select a match from the matches list
- Choose new teams from dropdown menus
- Teams can be set to null (TBD) if needed
- Changes are applied immediately

### 2. Edit Match Progression

Modify where teams advance after winning or losing a match.

- Select a match from the matches list
- Set winner advancement target match
- Set loser advancement target match
- Progression targets can be cleared (set to null)

### 3. Add New Match

Create additional matches in the tournament bracket.

- Specify match details (stage type, round type, etc.)
- Set match order and station assignment
- New matches get auto-assigned match IDs
- Can be used to extend brackets or add playoff rounds

## API Endpoints

### Update Match Teams
```
PUT /api/tournaments/{tournament_id}/edit/match/{match_id}/teams
```

**Body:**
```json
{
  "team1_id": 123,
  "team2_id": 456
}
```

### Update Match Progression
```
PUT /api/tournaments/{tournament_id}/edit/match/{match_id}/progression
```

**Body:**
```json
{
  "winner_advances_to_match_id": 789,
  "loser_advances_to_match_id": 101
}
```

### Add New Match
```
POST /api/tournaments/{tournament_id}/edit/matches
```

**Body:**
```json
{
  "stage_type": "Finals",
  "round_type": "Winners", 
  "round_number": 1,
  "position_in_round": 1,
  "stage_match_number": 1,
  "match_order": 10,
  "station_assignment": 1,
  "team1_id": null,
  "team2_id": null,
  "winner_advances_to_match_id": null,
  "loser_advances_to_match_id": null
}
```

## Usage Instructions

1. Navigate to Admin panel
2. Click "Tournament Edit" tab
3. Select an in-progress tournament from the list
4. Choose edit mode:
   - **Edit Teams**: Modify team assignments
   - **Edit Progression**: Change advancement paths  
   - **Add Match**: Create new matches
5. Select a match from the left panel (for edit modes)
6. Make changes in the right panel
7. Click update/add button to save changes

## Technical Notes

- Only tournaments with status "In_Progress" are available for editing
- Match IDs are auto-generated when adding new matches
- All changes are immediately persisted to the database
- Frontend refreshes data after successful updates
- Authentication is required (Admin or Director role)

## Testing

Run the test script to verify endpoints:

```bash
python3 test_tournament_edit.py
```

Make sure the backend server is running on localhost:5000 before testing.
