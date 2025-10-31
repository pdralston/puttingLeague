from flask import Blueprint, jsonify, request
from database import db
from models import Tournament, Team, Match
from sqlalchemy import text
from typing import List
import math
from decimal import Decimal

matches_bp = Blueprint('matches', __name__)

@matches_bp.route('/api/tournaments/<int:tournament_id>/matches/<int:match_id>/start', methods=['POST'])
def start_match(tournament_id, match_id):
    match = Match.query.filter_by(tournament_id=tournament_id, match_id=match_id).first()
    if not match:
        return jsonify({'error': 'Match not found'}), 404
    
    if match.match_status != 'Scheduled':
        return jsonify({'error': 'Match is not scheduled'}), 400
    
    # Find first available station (1-6)
    occupied_stations = db.session.query(Match.station_assignment).filter(
        Match.tournament_id == tournament_id,
        Match.match_status == 'In_Progress'
    ).all()
    
    occupied = {station[0] for station in occupied_stations if station[0]}
    available_station = next((i for i in range(1, 7) if i not in occupied), None)
    
    if not available_station:
        return jsonify({'error': 'No stations available'}), 400
    
    match.match_status = 'In_Progress'
    match.station_assignment = available_station
    
    try:
        db.session.commit()
        return jsonify({
            'match_id': match.match_id,
            'status': match.match_status,
            'station': match.station_assignment
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@matches_bp.route('/api/tournaments/<int:tournament_id>/matches/<int:match_id>/score', methods=['POST'])
def score_match(tournament_id, match_id):
    data = request.get_json()
    
    match = Match.query.filter_by(tournament_id=tournament_id, match_id=match_id).first()
    if not match:
        return jsonify({'error': 'Match not found'}), 404
    
    print(f"Debug - Match {match_id}: status={match.match_status}, team1_id={match.team1_id}, team2_id={match.team2_id}")
    
    # Allow advancement for bye matches (Pending/Scheduled/Completed) or regular matches (In_Progress)
    if match.team2_id is None:
        # Bye match - allow if Pending, Scheduled, or Completed
        if match.match_status not in ['Pending', 'Scheduled']:
            print(f"Debug - Bye match status check failed: {match.match_status}")
            return jsonify({'error': f'Bye match cannot be advanced (status: {match.match_status})'}), 400
    else:
        # Regular match - must be In_Progress
        if match.match_status != 'In_Progress':
            print(f"Debug - Regular match status check failed: {match.match_status}")
            return jsonify({'error': 'Match is not in progress'}), 400
    
    # Handle bye matches (only one team)
    if match.team2_id is None:
        print(f"Debug - Processing bye match {match_id}, team1_id: {match.team1_id}")
        if not match.team1_id:
            return jsonify({'error': 'No team to advance'}), 400
        
        match.team1_score = 1
        match.team2_score = 0
        match.match_status = 'Completed'
        match.station_assignment = None
        
        winner_team_id = match.team1_id
        loser_team_id = None
        print(f"Debug - Bye match completed, winner: {winner_team_id}")
    else:
        # Regular match with two teams
        if not data or 'team1_score' not in data or 'team2_score' not in data:
            return jsonify({'error': 'Missing score data'}), 400
        
        team1_score = int(data['team1_score'])
        team2_score = int(data['team2_score'])
        
        match.team1_score = team1_score
        match.team2_score = team2_score
        match.match_status = 'Completed'
        match.station_assignment = None
        
        # Determine winner and loser
        if team1_score > team2_score:
            winner_team_id = match.team1_id
            loser_team_id = match.team2_id
        else:
            winner_team_id = match.team2_id
            loser_team_id = match.team1_id
    
    # Advance teams to next matches
    if match.winner_advances_to_match_id and winner_team_id:
        print(f"Debug - Advancing winner {winner_team_id} to match {match.winner_advances_to_match_id}")
        next_match = Match.query.filter_by(tournament_id=tournament_id, match_id=match.winner_advances_to_match_id).first()
        if next_match:
            if not next_match.team1_id:
                next_match.team1_id = winner_team_id
                print(f"Debug - Set team1_id to {winner_team_id} in match {next_match.match_id}")
            elif not next_match.team2_id:
                next_match.team2_id = winner_team_id
                print(f"Debug - Set team2_id to {winner_team_id} in match {next_match.match_id}")
            
            # Update status to Scheduled if both teams are now assigned
            if next_match.team1_id and next_match.team2_id and next_match.match_status == 'Pending':
                next_match.match_status = 'Scheduled'
    
    if match.loser_advances_to_match_id and loser_team_id:
        next_match = Match.query.filter_by(tournament_id=tournament_id, match_id=match.loser_advances_to_match_id).first()
        if next_match:
            if not next_match.team1_id:
                next_match.team1_id = loser_team_id
            elif not next_match.team2_id:
                next_match.team2_id = loser_team_id
            
            # Update status to Scheduled if both teams are now assigned
            if next_match.team1_id and next_match.team2_id and next_match.match_status == 'Pending':
                next_match.match_status = 'Scheduled'
    
    # Auto-advance matches with only one parent that's completed
    _auto_advance_byes(tournament_id)
    
    # Handle championship match completion
    print(f"Debug - Match {match_id} completed: round_type={match.round_type}")
    if match.round_type == 'Championship':
        print(f"Debug - Processing championship completion")
        _handle_championship_completion(match, winner_team_id, loser_team_id)
    else:
        # Check if this completes the tournament (no more matches to play)
        remaining_matches = Match.query.filter_by(
            tournament_id=tournament_id, 
            match_status='Pending'
        ).filter(Match.team1_id.isnot(None)).count()
        
        scheduled_matches = Match.query.filter_by(
            tournament_id=tournament_id, 
            match_status='Scheduled'
        ).count()
        
        print(f"Debug - Remaining matches: {remaining_matches}, Scheduled: {scheduled_matches}")
        
        if remaining_matches == 0 and scheduled_matches == 0:
            print(f"Debug - No more matches, completing tournament")
            tournament = Tournament.query.get(tournament_id)
            tournament.status = 'Completed'
            _process_tournament_completion(tournament_id)
    
    try:
        
        db.session.commit()
        return jsonify({
            'match_id': match.match_id,
            'status': match.match_status,
            'team1_score': match.team1_score,
            'team2_score': match.team2_score,
            'winner_team_id': winner_team_id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@matches_bp.route('/api/tournaments/<int:tournament_id>/generate-matches', methods=['POST'])
def generate_matches(tournament_id):
    tournament = Tournament.query.get(tournament_id)
    if not tournament:
        return jsonify({'error': 'Tournament not found'}), 404
    
    if tournament.status != 'Scheduled':
        return jsonify({'error': f'Cannot generate matches for tournament with status: {tournament.status}'}), 400
    
    # Get teams for this tournament
    teams = Team.query.filter_by(tournament_id=tournament_id).all()
    if not teams:
        return jsonify({'error': 'No teams found for tournament'}), 400
    
    team_count = len(teams)
    matches = _generate_winners_bracket(tournament_id, teams, 1)
    _generate_losers_bracket(matches)
    
    # Bulk insert all matches
    db.session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
    db.session.add_all(matches)
    db.session.commit()
    db.session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    
    return jsonify({
        'tournament_id': tournament_id,
        'matches_created': len(matches)
    }), 201
    

def _generate_winners_bracket(tournament_id: int, teams: List[Team], start_order: int) -> List[Match]:
    """Generate winners bracket matches"""
    import random
    
    team_count = len(teams)
    if team_count < 4:
        raise ValueError("Need at least 4 teams")
    
    random.shuffle(teams)
    
    # Calculate bracket size (next power of 2)
    bracket_size = 1 << (team_count - 1).bit_length()
    wb_rounds = int(math.log2(bracket_size))
    
    matches = []
    match_id = start_order
    wb_matches = []
    
    # Create winners bracket matches
    for round_num in range(wb_rounds):
        matches_in_round = bracket_size >> (round_num + 1)
        round_matches = []
        for pos in range(matches_in_round):
            match = {
                'id': match_id,
                'round_num': round_num,
                'position': pos,
                'winner_to': None,
                'loser_to': None
            }
            matches.append(match)
            round_matches.append(match)
            match_id += 1
        wb_matches.append(round_matches)
    
    # Set winner advancement paths
    for match in matches:
        round_num = match['round_num']
        pos = match['position']
        
        if round_num < wb_rounds - 1:
            next_pos = pos // 2
            next_match = wb_matches[round_num + 1][next_pos]
            match['winner_to'] = next_match['id']
            
            # Set parent relationship
            if next_match.get('parent_match_id_one') is None:
                next_match['parent_match_id_one'] = match['id']
            else:
                next_match['parent_match_id_two'] = match['id']
    
    # Convert to database objects and filter out empty matches
    # Convert to database objects
    db_matches = []
    for match in matches:
        db_match = Match(
            tournament_id=tournament_id,
            match_id=match['id'],
            stage_type='Group_A',
            round_type='Winners',
            round_number=match['round_num'],
            position_in_round=match['position'],
            stage_match_number=match['id'],
            match_order=match['id'],
            winner_advances_to_match_id=match['winner_to'],
            loser_advances_to_match_id=match['loser_to'],
            parent_match_id_one=match.get('parent_match_id_one'),
            parent_match_id_two=match.get('parent_match_id_two'),
            match_status='Pending'
        )
        
        # Seed teams into first round with byes system
        if match['round_num'] == 0:
            pos = match['position']
            team1_idx = pos * 2
            team2_idx = pos * 2 + 1
            
            if team1_idx < team_count:
                db_match.team1_id = teams[team1_idx].team_id
                
                if team2_idx < team_count:
                    # Regular match - both teams present
                    db_match.team2_id = teams[team2_idx].team_id
                    db_match.match_status = 'Scheduled'
                else:
                    # Bye - only team1, auto-advance
                    db_match.match_status = 'Completed'
                    db_match.team1_score = 1
                    db_match.team2_score = 0
        
        db_matches.append(db_match)

    # Process byes - advance winners automatically
    _process_byes(db_matches)
    
    return db_matches

def _trim_empty_first_round(matches: List[Match]) -> List[Match]:
    """Remove matches that have no teams assigned or no valid incoming paths"""
    matches_to_remove = []
    
    for match in matches:
        should_remove = False
        
        if match.round_number == 0 and match.round_type == 'Winners':
            # Remove winners bracket first-round matches with no teams
            if match.team1_id is None and match.team2_id is None:
                should_remove = True
                
        elif match.round_type == 'Losers':
            # Remove losers bracket matches with no incoming paths from existing matches
            has_incoming = any(m.loser_advances_to_match_id == match.match_id 
                             for m in matches if m != match and m not in matches_to_remove)
            if not has_incoming:
                should_remove = True
        
        if should_remove:
            matches_to_remove.append(match)
    
    return [m for m in matches if m not in matches_to_remove]
    
    # Process byes - advance winners automatically
    _process_byes(db_matches)
    
    return db_matches

def _process_byes(matches: List[Match]) -> None:
    """Process bye matches and advance winners to next round"""
    bye_matches = [m for m in matches if m.match_status == 'Completed' and m.team2_id is None]
    
    for bye_match in bye_matches:
        if bye_match.winner_advances_to_match_id:
            next_match = next((m for m in matches if m.match_id == bye_match.winner_advances_to_match_id), None)
            if next_match:
                if next_match.team1_id is None:
                    next_match.team1_id = bye_match.team1_id
                elif next_match.team2_id is None:
                    next_match.team2_id = bye_match.team1_id
                    # If both teams are now assigned, schedule the match
                    if next_match.team1_id and next_match.team2_id:
                        next_match.match_status = 'Scheduled'

def _generate_losers_bracket(matches: List[Match]) -> None:
    """Generate losers bracket based on existing winners bracket"""
    if not matches:
        raise ValueError("No winners bracket found")
    
    start_match_id = matches[-1].match_id
    tournament_id = matches[-1].tournament_id
    
    # Calculate bracket parameters
    team_count = len([m for m in matches if m.round_number == 0]) * 2
    num_lb_rounds = int(2 * math.log2(team_count) - 1)
    
    # Generate losers bracket matches
    lb_matches = []
    match_id = start_match_id + 1
    wb_round_match_count = team_count / 2
    lb_round_match_count = wb_round_match_count / 2
    
    for round_num in range(num_lb_rounds):
        matches_for_round = int(wb_round_match_count / 2 if round_num % 2 == 0 else lb_round_match_count)
        
        if round_num % 2 == 0:
            wb_round_match_count /= 2
            lb_round_match_count = matches_for_round
        
        for pos in range(matches_for_round):
            lb_match = Match(
                tournament_id=tournament_id,
                match_id=match_id,
                stage_type='Group_A',
                round_type='Losers',
                round_number=round_num,
                position_in_round=pos,
                stage_match_number=match_id,
                match_order=match_id,
                match_status='Pending'
            )
            lb_matches.append(lb_match)
            match_id += 1
    
    # Group matches by round for easier access
    wb_by_round = {}
    lb_by_round = {}
    
    for match in matches:
        wb_by_round.setdefault(match.round_number, []).append(match)
    
    for match in lb_matches:
        lb_by_round.setdefault(match.round_number, []).append(match)
    
    # Set WB loser advancement paths
    _set_wb_loser_paths(wb_by_round, lb_by_round)
    
    # Set LB internal progression
    _set_lb_progression(lb_by_round)
    
    matches.extend(lb_matches)

def _set_wb_loser_paths(wb_by_round: dict, lb_by_round: dict) -> None:
    """Set advancement paths from winners bracket to losers bracket"""
    # Round 0 losers go to LB round 0
    wb_first_round = wb_by_round[0]
    lb_first_round = lb_by_round[0] if 0 in lb_by_round else []
    
    for i in range(0, len(wb_first_round), 2):
        pos = i // 2
        if pos < len(lb_first_round):  # Check bounds
            wb_first_round[i].loser_advances_to_match_id = lb_first_round[pos].match_id
            if i + 1 < len(wb_first_round):
                wb_first_round[i + 1].loser_advances_to_match_id = lb_first_round[pos].match_id
    
    # Subsequent WB losers
    loser_round_adjust = 0
    for wb_round in range(1, len(wb_by_round)):
        for pos, match in enumerate(wb_by_round[wb_round]):
            lb_round = wb_round + loser_round_adjust
            if lb_round < len(lb_by_round) and pos < len(lb_by_round[lb_round]):
                next_match = lb_by_round[lb_round][pos]
                match.loser_advances_to_match_id = next_match.match_id
                if next_match.parent_match_id_one is None:
                    next_match.parent_match_id_one = match.match_id
                else:
                    next_match.parent_match_id_two = match.match_id
        loser_round_adjust += 1

def _set_lb_progression(lb_by_round: dict) -> None:
    """Set internal losers bracket progression"""
    for round_num in range(len(lb_by_round) - 1):
        for match in lb_by_round[round_num]:
            next_pos = match.position_in_round // 2
            if next_pos < len(lb_by_round[round_num + 1]):
                next_match = lb_by_round[round_num + 1][next_pos]
                match.winner_advances_to_match_id = next_match.match_id
                if next_match.parent_match_id_one is None:
                    next_match.parent_match_id_one = match.match_id
                else:
                    next_match.parent_match_id_two = match.match_id
  

@matches_bp.route('/api/matches/<int:match_id>/score', methods=['PUT'])
def update_match_score(match_id):
    if match_id <= 0:
        return jsonify({'error': 'Invalid match ID'}), 400
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Score data required'}), 400
    
    match = Match.query.get(match_id)
    if not match:
        return jsonify({'error': 'Match not found'}), 404
    
    # Validate tournament exists and is in correct state
    tournament = Tournament.query.get(match.tournament_id)
    if not tournament:
        return jsonify({'error': 'Tournament not found'}), 404
    
    if tournament.status not in ['Scheduled', 'In_Progress']:
        return jsonify({'error': f'Cannot score matches for tournament with status: {tournament.status}'}), 400
    
    # Validate scores
    try:
        team1_score = int(data.get('team1_score', 0))
        team2_score = int(data.get('team2_score', 0))
        if team1_score < 0 or team2_score < 0:
            return jsonify({'error': 'Scores must be non-negative'}), 400
        if team1_score == team2_score:
            return jsonify({'error': 'Matches cannot end in a tie'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid score format'}), 400
    
    # Check if this is a re-score (editing existing result)
    is_rescore = match.match_status == 'Completed'
    old_winner_team_id = None
    old_loser_team_id = None
    
    if is_rescore:
        # Store old results for rollback
        old_winner_team_id = match.team1_id if match.team1_score > match.team2_score else match.team2_id
        old_loser_team_id = match.team2_id if match.team1_score > match.team2_score else match.team1_id
    
    # Update match scores
    match.team1_score = team1_score
    match.team2_score = team2_score
    match.match_status = 'Completed'
    
    # Determine new winner and loser
    winner_team_id = match.team1_id if team1_score > team2_score else match.team2_id
    loser_team_id = match.team2_id if team1_score > team2_score else match.team1_id
    
    advancement_results = []
    rollback_results = []
    
    # Handle re-scoring: rollback previous advancements if winner changed
    if is_rescore and (old_winner_team_id != winner_team_id):
        rollback_results = _rollback_match_advancements(match, old_winner_team_id, old_loser_team_id)
    
    # Advance teams based on new results (only if slots are available)
    if match.winner_advances_to_match_id:
        winner_advanced = _advance_team_to_match(winner_team_id, match.winner_advances_to_match_id)
        if winner_advanced:
            advancement_results.append({
                'team_id': winner_team_id,
                'type': 'winner',
                'advanced_to_match_id': match.winner_advances_to_match_id
            })
    
    if match.loser_advances_to_match_id:
        loser_advanced = _advance_team_to_match(loser_team_id, match.loser_advances_to_match_id)
        if loser_advanced:
            advancement_results.append({
                'team_id': loser_team_id,
                'type': 'loser',
                'advanced_to_match_id': match.loser_advances_to_match_id
            })
    
    # Handle championship match completion
    if match.round_type == 'Championship':
        _handle_championship_completion(match, winner_team_id, loser_team_id)
    
    db.session.commit()
    
    return jsonify({
        'match_id': match.match_id,
        'team1_score': match.team1_score,
        'team2_score': match.team2_score,
        'match_status': match.match_status,
        'winner_team_id': winner_team_id,
        'loser_team_id': loser_team_id,
        'is_rescore': is_rescore,
        'advancements': advancement_results,
        'rollbacks': rollback_results
    })

def _rollback_match_advancements(match, old_winner_id, old_loser_id):
    """Remove teams from subsequent matches when re-scoring"""
    
    rollbacks = []
    
    # Remove old winner from winner advancement match
    if match.winner_advances_to_match_id:
        target_match = Match.query.get(match.winner_advances_to_match_id)
        if target_match:
            if target_match.team1_id == old_winner_id:
                target_match.team1_id = None
                rollbacks.append({'team_id': old_winner_id, 'removed_from_match_id': target_match.match_id})
            elif target_match.team2_id == old_winner_id:
                target_match.team2_id = None
                rollbacks.append({'team_id': old_winner_id, 'removed_from_match_id': target_match.match_id})
    
    # Remove old loser from loser advancement match
    if match.loser_advances_to_match_id:
        target_match = Match.query.get(match.loser_advances_to_match_id)
        if target_match:
            if target_match.team1_id == old_loser_id:
                target_match.team1_id = None
                rollbacks.append({'team_id': old_loser_id, 'removed_from_match_id': target_match.match_id})
            elif target_match.team2_id == old_loser_id:
                target_match.team2_id = None
                rollbacks.append({'team_id': old_loser_id, 'removed_from_match_id': target_match.match_id})
    
    return rollbacks

def _advance_team_to_match(team_id, target_match_id):
    """Advance a team to the next match"""
    target_match = Match.query.filter_by(match_id=target_match_id).first()
    if not target_match:
        return False
    
    # Place team in first available slot
    if target_match.team1_id is None:
        target_match.team1_id = team_id
        return True
    elif target_match.team2_id is None:
        target_match.team2_id = team_id
        return True
    
    # Both slots filled - match is ready
    return False

def _auto_advance_byes(tournament_id):
    """Auto-advance teams in matches that have only one parent completed or one team seeded"""
    matches = Match.query.filter_by(tournament_id=tournament_id).all()
    
    for match in matches:
        if match.match_status not in ['Pending', 'Scheduled']:
            continue
        
        # Case 1: Check parent-based advancement for true byes
        parent_winner = None
        parent_loser = None
        
        if match.parent_match_id_one:
            parent_winner = Match.query.filter_by(tournament_id=tournament_id, match_id=match.parent_match_id_one).first()
        if match.parent_match_id_two:
            parent_loser = Match.query.filter_by(tournament_id=tournament_id, match_id=match.parent_match_id_two).first()
            
        # Count completed parents
        completed_parents = 0
        advancing_team_id = None
        
        if parent_winner and parent_winner.match_status == 'Completed':
            completed_parents += 1
            # For losers bracket matches, we want the loser from winners bracket
            if match.round_type == 'Losers' and parent_winner.round_type == 'Winners':
                advancing_team_id = parent_winner.team2_id if parent_winner.team1_score > parent_winner.team2_score else parent_winner.team1_id
            else:
                advancing_team_id = parent_winner.team1_id if parent_winner.team1_score > parent_winner.team2_score else parent_winner.team2_id
            
        if parent_loser and parent_loser.match_status == 'Completed':
            completed_parents += 1
            # For losers bracket, this is typically another losers bracket match, so we want the winner
            advancing_team_id = parent_loser.team1_id if parent_loser.team1_score > parent_loser.team2_score else parent_loser.team2_id
        
        # Auto-advance if only one parent exists and is completed
        total_parents = (1 if match.parent_match_id_one else 0) + (1 if match.parent_match_id_two else 0)
        
        if total_parents == 1 and completed_parents == 1 and advancing_team_id:
            match.team1_id = advancing_team_id
            match.team1_score = 1
            match.team2_score = 0
            match.match_status = 'Completed'
            
            # Advance to next match
            if match.winner_advances_to_match_id:
                _advance_team_to_match(advancing_team_id, match.winner_advances_to_match_id)

def _handle_championship_completion(match, winner_team_id, loser_team_id):
    """Handle championship match completion - either end tournament or create final match"""
    from models import Tournament, Team, TeamHistory
    
    # Check if this was WB winner vs LB winner (first championship match)
    if match.round_number == 0:
        # If WB winner won (team1), tournament is complete
        if winner_team_id == match.team1_id:
            tournament = Tournament.query.get(match.tournament_id)
            tournament.status = 'Completed'
            _process_tournament_completion(match.tournament_id)
        else:
            # LB winner won, create final championship match
            next_match_id = match.match_id + 1
            
            final_match = Match(
                tournament_id=match.tournament_id,
                match_id=next_match_id,
                stage_type='Finals',
                round_type='Championship',
                round_number=1,
                position_in_round=0,
                stage_match_number=next_match_id,
                match_order=next_match_id,
                team1_id=match.team1_id,  # WB winner gets another chance
                team2_id=match.team2_id,  # LB winner 
                match_status='Scheduled'
            )
            db.session.add(final_match)
    else:
        # This was the final championship match, tournament is complete
        tournament = Tournament.query.get(match.tournament_id)
        tournament.status = 'Completed'
        _process_tournament_completion(match.tournament_id)

def _process_tournament_completion(tournament_id):
    """Process all completion tasks for a tournament"""
    _calculate_final_places(tournament_id)
    _update_teammate_history(tournament_id)
    _update_seasonal_points(tournament_id)
    _distribute_cash_payouts(tournament_id)

def _calculate_final_places(tournament_id):
    """Calculate and set final places for all teams"""
    from models import Team
    
    # Find championship matches to determine 1st and 2nd
    championship_matches = Match.query.filter_by(
        tournament_id=tournament_id, 
        round_type='Championship',
        match_status='Completed'
    ).order_by(Match.round_number.desc()).all()
    
    if championship_matches:
        final_match = championship_matches[0]
        
        # Determine winner and runner-up from final championship match
        if final_match.team1_score > final_match.team2_score:
            winner_team_id = final_match.team1_id
            runner_up_team_id = final_match.team2_id
        else:
            winner_team_id = final_match.team2_id
            runner_up_team_id = final_match.team1_id
            
        # Set final places
        winner_team = Team.query.filter_by(tournament_id=tournament_id, team_id=winner_team_id).first()
        runner_up_team = Team.query.filter_by(tournament_id=tournament_id, team_id=runner_up_team_id).first()
        
        if winner_team:
            winner_team.final_place = 1
        if runner_up_team:
            runner_up_team.final_place = 2
    
    # Calculate places for eliminated teams based on elimination order
    _calculate_elimination_places(tournament_id)

def _calculate_elimination_places(tournament_id):
    """Calculate final places for teams based on when they were eliminated"""
    from models import Team
    
    # Get all matches in reverse order (latest eliminations first)
    matches = Match.query.filter_by(tournament_id=tournament_id, match_status='Completed').order_by(Match.match_order.desc()).all()
    
    current_place = 3  # Start with 3rd place (1st and 2nd set by championship)
    
    for match in matches:
        # Skip championship matches (already handled)
        if match.round_type == 'Championship':
            continue
            
        # Find the losing team
        if match.team1_score < match.team2_score:
            losing_team_id = match.team1_id
        else:
            losing_team_id = match.team2_id
            
        # Set final place if not already set
        losing_team = Team.query.filter_by(tournament_id=tournament_id, team_id=losing_team_id).first()
        if losing_team and not losing_team.final_place:
            losing_team.final_place = current_place
            current_place += 1

def _update_teammate_history(tournament_id):
    """Update teammate history for all teams in completed tournament"""
    from models import Team, TeamHistory
    
    teams = Team.query.filter_by(tournament_id=tournament_id).all()
    
    for team in teams:
        if not team.is_ghost_team and team.player2_id:
            # Update history for both players
            for player_id, teammate_id in [(team.player1_id, team.player2_id), (team.player2_id, team.player1_id)]:
                history = TeamHistory.query.filter_by(player_id=player_id, teammate_id=teammate_id).first()
                
                if history:
                    history.times_paired += 1
                else:
                    history = TeamHistory(
                        player_id=player_id,
                        teammate_id=teammate_id,
                        times_paired=1,
                        average_place=None
                    )
                    db.session.add(history)

def _update_seasonal_points(tournament_id):
    """Update seasonal points for all players in tournament"""
    from models import RegisteredPlayer, TournamentRegistration
    
    registrations = TournamentRegistration.query.filter_by(tournament_id=tournament_id).all()
    
    for reg in registrations:
        player = RegisteredPlayer.query.get(reg.player_id)
        if player:
            # Calculate points: 1 for participation + match wins + top 4 bonus + undefeated bonus
            participation_points = 1
            match_wins = _count_match_wins(tournament_id, reg.player_id)
            top_4_bonus = 2 if _is_top_4_finish(tournament_id, reg.player_id) else 0
            undefeated_bonus = 3 if _is_undefeated(tournament_id, reg.player_id) else 0
            
            total_points = participation_points + match_wins + top_4_bonus + undefeated_bonus
            player.seasonal_points += total_points

def _distribute_cash_payouts(tournament_id):
    """Calculate and distribute cash payouts to players"""
    from models import RegisteredPlayer, TournamentRegistration, Team, AcePot
    
    registrations = TournamentRegistration.query.filter_by(tournament_id=tournament_id).all()
    total_participants = len(registrations)
    total_payout_pot = 5 * total_participants
    
    # Get total ace pot balance across all tournaments
    ace_pot_balance = db.session.query(db.func.sum(AcePot.amount)).scalar() or 0
    
    # Find 1st and 2nd place teams
    first_place_team = Team.query.filter_by(tournament_id=tournament_id, final_place=1).first()
    second_place_team = Team.query.filter_by(tournament_id=tournament_id, final_place=2).first()
    
    # Calculate payouts
    second_place_payout = min(40, total_payout_pot - 40) if total_payout_pot > 40 else 0
    first_place_payout = total_payout_pot - second_place_payout
    
    # Check if first place went undefeated for ace pot
    ace_pot_payout = 0
    if first_place_team and _team_is_undefeated(tournament_id, first_place_team.team_id):
        ace_pot_payout = ace_pot_balance
        first_place_payout += ace_pot_payout
        
        # Update ace pot tracker
        if ace_pot_payout > 0:
            # Get player names for description
            from models import RegisteredPlayer
            player1 = RegisteredPlayer.query.get(first_place_team.player1_id)
            player2 = RegisteredPlayer.query.get(first_place_team.player2_id) if first_place_team.player2_id else None
            
            if player2 and not first_place_team.is_ghost_team:
                team_names = f"{player1.player_name} & {player2.player_name}"
            else:
                team_names = player1.player_name
            
            payout_entry = AcePot(
                tournament_id=tournament_id,
                date=db.func.current_date(),
                description=f'Ace pot payout to {team_names}',
                amount=-ace_pot_payout
            )
            db.session.add(payout_entry)
    
    # Distribute cash to players
    for reg in registrations:
        player = RegisteredPlayer.query.get(reg.player_id)
        if player:
            player_team = Team.query.filter_by(tournament_id=tournament_id).filter(
                db.or_(Team.player1_id == reg.player_id, Team.player2_id == reg.player_id)
            ).first()
            
            if player_team:
                teammates_count = 2 if player_team.player2_id and not player_team.is_ghost_team else 1
                
                if player_team.final_place == 1:
                    player.seasonal_cash += Decimal(str(first_place_payout / teammates_count))
                elif player_team.final_place == 2:
                    player.seasonal_cash += Decimal(str(second_place_payout / teammates_count))

def _count_match_wins(tournament_id, player_id):
    """Count matches won by player's team"""
    from models import Team
    
    # Find teams this player was on
    teams = Team.query.filter_by(tournament_id=tournament_id).filter(
        db.or_(Team.player1_id == player_id, Team.player2_id == player_id)
    ).all()
    
    wins = 0
    for team in teams:
        matches = Match.query.filter_by(tournament_id=tournament_id).filter(
            db.or_(Match.team1_id == team.team_id, Match.team2_id == team.team_id)
        ).filter(Match.match_status == 'Completed').all()
        
        for match in matches:
            if ((match.team1_id == team.team_id and match.team1_score > match.team2_score) or
                (match.team2_id == team.team_id and match.team2_score > match.team1_score)):
                wins += 1
    
    return wins

def _is_top_4_finish(tournament_id, player_id):
    """Check if player finished in top 4"""
    from models import Team
    
    team = Team.query.filter_by(tournament_id=tournament_id).filter(
        db.or_(Team.player1_id == player_id, Team.player2_id == player_id)
    ).first()
    
    return team and team.final_place and team.final_place <= 4

def _is_undefeated(tournament_id, player_id):
    """Check if player's team went undefeated"""
    from models import Team
    
    teams = Team.query.filter_by(tournament_id=tournament_id).filter(
        db.or_(Team.player1_id == player_id, Team.player2_id == player_id)
    ).all()
    
    for team in teams:
        matches = Match.query.filter_by(tournament_id=tournament_id).filter(
            db.or_(Match.team1_id == team.team_id, Match.team2_id == team.team_id)
        ).filter(Match.match_status == 'Completed').all()
        
        for match in matches:
            # If team lost any match, not undefeated
            if ((match.team1_id == team.team_id and match.team1_score < match.team2_score) or
                (match.team2_id == team.team_id and match.team2_score < match.team1_score)):
                return False
    
    return True

def _team_is_undefeated(tournament_id, team_id):
    """Check if specific team went undefeated"""
    matches = Match.query.filter_by(tournament_id=tournament_id).filter(
        db.or_(Match.team1_id == team_id, Match.team2_id == team_id)
    ).filter(Match.match_status == 'Completed').all()
    
    for match in matches:
        # If team lost any match, not undefeated
        if ((match.team1_id == team_id and match.team1_score < match.team2_score) or
            (match.team2_id == team_id and match.team2_score < match.team1_score)):
            return False
    
    return True

@matches_bp.route('/api/tournaments/<int:tournament_id>/create-championship', methods=['POST'])
def create_championship_round(tournament_id):
    tournament = Tournament.query.get(tournament_id)
    if not tournament:
        return jsonify({'error': 'Tournament not found'}), 404
    
    # Get the highest match_id to continue numbering
    last_match = Match.query.filter_by(tournament_id=tournament_id).order_by(Match.match_id.desc()).first()
    next_match_id = (last_match.match_id + 1) if last_match else 1
    
    # Create Championship Match 1 (WB winner vs LB winner)
    championship_1 = Match(
        tournament_id=tournament_id,
        match_id=next_match_id,
        stage_type='Finals',
        round_type='Championship',
        round_number=0,
        position_in_round=0,
        stage_match_number=next_match_id,
        match_order=next_match_id,
        match_status='Pending'
    )
    
    # Find and seed the survivors
    wb_final = Match.query.filter_by(tournament_id=tournament_id, round_type='Winners').order_by(Match.round_number.desc()).first()
    lb_final = Match.query.filter_by(tournament_id=tournament_id, round_type='Losers').order_by(Match.round_number.desc()).first()
    
    if wb_final and wb_final.match_status == 'Completed':
        wb_winner = wb_final.team1_id if wb_final.team1_score > wb_final.team2_score else wb_final.team2_id
        championship_1.team1_id = wb_winner
        
    if lb_final and lb_final.match_status == 'Completed':
        lb_winner = lb_final.team1_id if lb_final.team1_score > lb_final.team2_score else lb_final.team2_id
        championship_1.team2_id = lb_winner
        
    # If both teams are seeded, make it schedulable
    if championship_1.team1_id and championship_1.team2_id:
        championship_1.match_status = 'Scheduled'
    
    db.session.add(championship_1)
    db.session.commit()
    
    return jsonify({
        'tournament_id': tournament_id,
        'championship_match_1': championship_1.match_id,
        'message': 'Championship match created'
    }), 201