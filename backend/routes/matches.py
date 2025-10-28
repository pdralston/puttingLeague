from flask import Blueprint, jsonify, request
from database import db
from models import Tournament, Team, Match
from typing import List
import math

matches_bp = Blueprint('matches', __name__)

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
    db.session.add_all(matches)
    db.session.commit()
    
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
            match['winner_to'] = wb_matches[round_num + 1][next_pos]['id']
    
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
            match_status='Pending'
        )
        
        # Seed teams into first round
        if match['round_num'] == 0:
            pos = match['position']
            if pos * 2 < team_count:
                db_match.team1_id = teams[pos * 2].team_id
                if pos * 2 + 1 < team_count:
                    db_match.team2_id = teams[pos * 2 + 1].team_id
                    db_match.match_status = 'Scheduled'
        
        db_matches.append(db_match)
    
    return db_matches

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
    for i in range(0, len(wb_by_round[0]), 2):
        pos = i // 2
        wb_by_round[0][i].loser_advances_to_match_id = lb_by_round[0][pos].match_id
        if i + 1 < len(wb_by_round[0]):
            wb_by_round[0][i + 1].loser_advances_to_match_id = lb_by_round[0][pos].match_id
    
    # Subsequent WB losers
    loser_round_adjust = 0
    for wb_round in range(1, len(wb_by_round)):
        for pos, match in enumerate(wb_by_round[wb_round]):
            lb_round = wb_round + loser_round_adjust
            if lb_round < len(lb_by_round) and pos < len(lb_by_round[lb_round]):
                match.loser_advances_to_match_id = lb_by_round[lb_round][pos].match_id
        loser_round_adjust += 1

def _set_lb_progression(lb_by_round: dict) -> None:
    """Set internal losers bracket progression"""
    for round_num in range(len(lb_by_round) - 1):
        for match in lb_by_round[round_num]:
            next_pos = match.position_in_round // 2
            if next_pos < len(lb_by_round[round_num + 1]):
                match.winner_advances_to_match_id = lb_by_round[round_num + 1][next_pos].match_id
  

@matches_bp.route('/api/matches/<int:match_id>/score', methods=['PUT'])
def score_match(match_id):
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
    target_match = Match.query.get(target_match_id)
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