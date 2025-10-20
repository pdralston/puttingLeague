from flask import Blueprint, jsonify, request
from database import db
from models import Tournament, Team, Match
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
    if team_count <= 12:
        # Single group tournament
        matches = _generate_single_group_matches(tournament_id, teams, 1)
        db.session.commit()
        
        return jsonify({
            'tournament_id': tournament_id,
            'total_matches': len(matches),
            'team_count': team_count,
            'bracket_type': 'single_group',
            'matches': [{'match_id': m.stage_match_number, 'round_type': m.round_type, 'stage_type': m.stage_type} for m in matches]
        }), 201
    else:
        return jsonify({'error': 'Multi-group tournaments not yet implemented'}), 501
    

def _generate_single_group_matches(tournament_id, teams, start_order):
    """Generate complete single stage double elimination bracket"""
    import random
    
    team_count = len(teams)
    if team_count < 4:
        raise ValueError("Need at least 4 teams")
    
    random.shuffle(teams)
    matches = []
    match_id = start_order
    
    # Calculate structure
    wb_rounds = (team_count - 1).bit_length()
    lb_rounds = 2 * (wb_rounds - 1)
    
    # Create matches in chronological order
    for round_num in range(max(wb_rounds, lb_rounds + 1)):
        # Add WB matches for this round
        if round_num < wb_rounds:
            wb_matches_in_round = team_count // (2 ** (round_num + 1))
            for pos in range(wb_matches_in_round):
                matches.append({
                    'id': match_id,
                    'bracket': 'wb',
                    'round': round_num,
                    'position': pos,
                    'winner_advances_to': None,
                    'loser_advances_to': None
                })
                match_id += 1
        
        # Add LB matches for this round
        if round_num < lb_rounds:
            if round_num % 2 == 0:  # Dropdown round
                if round_num == 0:
                    lb_matches_in_round = team_count // 4  # WB R1 losers
                else:
                    lb_matches_in_round = 1  # Later dropdown rounds
            else:  # Elimination round
                lb_matches_in_round = team_count // (2 ** (round_num + 2))
            
            for pos in range(lb_matches_in_round):
                matches.append({
                    'id': match_id,
                    'bracket': 'lb',
                    'round': round_num,
                    'position': pos,
                    'winner_advances_to': None,
                    'loser_advances_to': None
                })
                match_id += 1
    
    # Add Championship match
    matches.append({
        'id': match_id,
        'bracket': 'championship',
        'round': 0,
        'position': 0,
        'winner_advances_to': None,
        'loser_advances_to': None
    })
    
    # Set advancement IDs
    for match in matches:
        if match['bracket'] == 'wb' and match['round'] < wb_rounds - 1:
            # WB winner advancement: (r+1, p//2)
            target_round = match['round'] + 1
            target_pos = match['position'] // 2
            for target in matches:
                if (target['bracket'] == 'wb' and 
                    target['round'] == target_round and 
                    target['position'] == target_pos):
                    match['winner_advances_to'] = target['id']
                    break
        
        # WB final winner goes to championship
        elif match['bracket'] == 'wb' and match['round'] == wb_rounds - 1:
            for target in matches:
                if target['bracket'] == 'championship':
                    match['winner_advances_to'] = target['id']
                    break
        
        # WB loser advancement to LB
        if match['bracket'] == 'wb':
            lb_target_round = 2 * match['round']  # WB R0→LB R0, WB R1→LB R2, etc.
            if lb_target_round < lb_rounds:
                target_pos = match['position'] // 2  # Distribute based on position
                for target in matches:
                    if (target['bracket'] == 'lb' and 
                        target['round'] == lb_target_round and
                        target['position'] == target_pos):
                        match['loser_advances_to'] = target['id']
                        break
            elif match['round'] == wb_rounds - 1:  # WB final loser
                for target in matches:
                    if target['bracket'] == 'championship':
                        match['loser_advances_to'] = target['id']
                        break
        
        # LB internal advancement
        elif match['bracket'] == 'lb':
            if match['round'] % 2 == 1:  # Elimination round
                if match['round'] < lb_rounds - 1:  # Not final LB round
                    target_round = match['round'] + 1
                    for target in matches:
                        if (target['bracket'] == 'lb' and 
                            target['round'] == target_round):
                            match['winner_advances_to'] = target['id']
                            break
                else:  # Final LB round goes to championship
                    for target in matches:
                        if target['bracket'] == 'championship':
                            match['winner_advances_to'] = target['id']
                            break
            else:  # Dropdown round
                target_round = match['round'] + 1
                if target_round < lb_rounds:
                    for target in matches:
                        if (target['bracket'] == 'lb' and 
                            target['round'] == target_round):
                            match['winner_advances_to'] = target['id']
                            break
    
    # Convert to Match objects
    db_matches = []
    for match_data in matches:
        round_type = 'Championship' if match_data['bracket'] == 'championship' else ('Winners' if match_data['bracket'] == 'wb' else 'Losers')
        
        match = Match(
            tournament_id=tournament_id,
            match_id=match_data['id'],
            stage_type='Group_A',
            round_type=round_type,
            stage_match_number=match_data['id'],
            match_order=match_data['id'],
            winner_advances_to_match_id=match_data['winner_advances_to'],
            loser_advances_to_match_id=match_data['loser_advances_to'],
            match_status='Pending'
        )
        
        # Seed first WB round with teams
        if match_data['bracket'] == 'wb' and match_data['round'] == 0:
            pos = match_data['position']
            if pos * 2 < len(teams):
                match.team1_id = teams[pos * 2].team_id
            if pos * 2 + 1 < len(teams):
                match.team2_id = teams[pos * 2 + 1].team_id
                match.match_status = 'Scheduled'
        
        db.session.add(match)
        db_matches.append(match)
    
    # Fix final LB match advancement: find highest ID losers match and set it to advance to championship
    championship_match = next(m for m in db_matches if m.round_type == 'Championship')
    final_lb_match = max((m for m in db_matches if m.round_type == 'Losers'), key=lambda x: x.match_id)
    final_lb_match.winner_advances_to_match_id = championship_match.match_id
    
    return db_matches

def _generate_group_matches(tournament_id, teams, stage_type, start_order):
    """Generate complete double elimination bracket for a group"""
    print("TODO: implement _generate_single_group_matches")

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
