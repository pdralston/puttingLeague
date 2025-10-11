from flask import Blueprint, jsonify, request
from database import db
from models import Tournament, Team, Match

matches_bp = Blueprint('matches', __name__)

@matches_bp.route('/api/tournaments/<int:tournament_id>/generate-matches', methods=['POST'])
def generate_matches(tournament_id):
    if tournament_id <= 0:
        return jsonify({'error': 'Invalid tournament ID'}), 400
    
    tournament = Tournament.query.get(tournament_id)
    if not tournament:
        return jsonify({'error': 'Tournament not found'}), 404
    
    teams = Team.query.filter_by(tournament_id=tournament_id).order_by(Team.seed_number).all()
    if not teams:
        return jsonify({'error': 'No teams found for this tournament'}), 400
    
    # Clear existing matches
    Match.query.filter_by(tournament_id=tournament_id).delete()
    
    matches = []
    match_order = 1
    all_bye_teams = []
    group_a_teams = []
    group_b_teams = []
    
    if len(teams) < 12:
        # Single stage double elimination for < 12 teams
        matches.extend(_generate_single_stage_matches(tournament_id, teams, match_order))
    else:
        # Multi-stage format for 12+ teams: Group A/B -> Finals
        mid_point = len(teams) // 2
        group_a_teams = teams[:mid_point]
        group_b_teams = teams[mid_point:]
        
        all_bye_teams = []
        
        # Generate Group A matches
        group_a_matches, group_a_byes = _generate_group_matches(tournament_id, group_a_teams, 'Group_A', match_order)
        matches.extend(group_a_matches)
        all_bye_teams.extend(group_a_byes)
        match_order += len(group_a_matches)
        
        # Generate Group B matches  
        group_b_matches, group_b_byes = _generate_group_matches(tournament_id, group_b_teams, 'Group_B', match_order)
        matches.extend(group_b_matches)
        all_bye_teams.extend(group_b_byes)
    
    db.session.commit()
    
    return jsonify({
        'tournament_id': tournament_id,
        'total_matches': len(matches),
        'total_teams': len(teams),
        'format': 'multi_stage' if len(teams) >= 12 else 'single_stage',
        'bye_teams': [{
            'team_id': t.team_id,
            'stage_type': 'Group_A' if t in group_a_teams else 'Group_B',
            'round': 1
        } for t in all_bye_teams] if len(teams) >= 12 else [],
        'matches': [{
            'match_id': m.match_id,
            'stage_type': m.stage_type,
            'round_type': m.round_type,
            'team1_id': m.team1_id,
            'team2_id': m.team2_id,
            'global_match_order': m.global_match_order,
            'match_status': m.match_status,
            'winner_advances_to_match_id': m.winner_advances_to_match_id,
            'loser_advances_to_match_id': m.loser_advances_to_match_id
        } for m in matches]
    }), 201

def _generate_single_stage_matches(tournament_id, teams, start_order):
    """Generate complete single stage double elimination bracket"""
    matches = []
    
    if len(teams) < 2:
        return matches
    
    # Calculate bracket size - next power of 2
    bracket_size = 1
    while bracket_size < len(teams):
        bracket_size *= 2
    
    # Generate winners bracket
    current_teams = bracket_size
    winners_rounds = []
    
    for round_num in range(1, bracket_size.bit_length()):
        matches_in_round = current_teams // 2
        round_matches = []
        
        for match_num in range(matches_in_round):
            if round_num == 1:
                # First round - assign actual teams or None for byes
                team1_id = teams[match_num * 2].team_id if match_num * 2 < len(teams) else None
                team2_id = teams[match_num * 2 + 1].team_id if match_num * 2 + 1 < len(teams) else None
                status = 'Scheduled' if team1_id and team2_id else 'Scheduled'
            else:
                # Later rounds - use None as placeholder
                team1_id = None
                team2_id = None
                status = 'Pending'
                
            match = Match(
                tournament_id=tournament_id,
                stage_type='Finals',
                round_type='Winners',
                stage_match_number=len(matches) + 1,
                global_match_order=start_order + len(matches),
                team1_id=team1_id,
                team2_id=team2_id,
                match_status=status
            )
            db.session.add(match)
            matches.append(match)
            round_matches.append(match)
        
        winners_rounds.append(round_matches)
        current_teams //= 2
    
    # Flush to get match IDs
    db.session.flush()
    
    # Set winner advancement - special logic for 3-team bracket
    if len(teams) == 3 and len(winners_rounds) >= 2:
        # Match 116 winner advances to Match 117 to face the bye team
        winners_rounds[0][0].winner_advances_to_match_id = winners_rounds[0][1].match_id
        # Match 117 winner advances to finals
        winners_rounds[0][1].winner_advances_to_match_id = winners_rounds[1][0].match_id
    else:
        # Standard advancement logic
        for round_idx in range(len(winners_rounds) - 1):
            for match_idx, match in enumerate(winners_rounds[round_idx]):
                next_match_idx = match_idx // 2
                if next_match_idx < len(winners_rounds[round_idx + 1]):
                    match.winner_advances_to_match_id = winners_rounds[round_idx + 1][next_match_idx].match_id
    
    # Set loser advancement from winners bracket to losers bracket
    losers_match = None
    winners_final = None
    
    for match in matches:
        if match.round_type == 'Losers':
            losers_match = match
        elif match.round_type == 'Winners' and match.team1_id is None and match.team2_id is None:
            winners_final = match
    
    if losers_match and winners_final:
        # All winners bracket matches send their losers to the losers bracket
        for winner_match in matches:
            if winner_match.round_type == 'Winners' and winner_match != winners_final:
                winner_match.loser_advances_to_match_id = losers_match.match_id
        
        # Winner of losers bracket advances to winners final
        losers_match.winner_advances_to_match_id = winners_final.match_id
    
    # Flush again to save loser advancement changes
    db.session.flush()
    
    # Generate losers bracket (simplified)
    if len(teams) > 2:
        losers_matches_needed = max(1, (len(teams) - 1) // 2)
        for match_num in range(losers_matches_needed):
            match = Match(
                tournament_id=tournament_id,
                stage_type='Finals',
                round_type='Losers',
                stage_match_number=len(matches) + 1,
                global_match_order=start_order + len(matches),
                team1_id=None,
                team2_id=None,
                match_status='Pending'
            )
            db.session.add(match)
            matches.append(match)
    
    return matches

def _generate_group_matches(tournament_id, teams, stage_type, start_order):
    """Generate complete double elimination bracket for a group"""
    matches = []
    bye_teams = []
    
    if len(teams) < 2:
        return matches, bye_teams
    
    # Calculate bracket size - next power of 2
    bracket_size = 1
    while bracket_size < len(teams):
        bracket_size *= 2
    
    # Generate winners bracket rounds
    current_teams = bracket_size
    
    for round_num in range(1, bracket_size.bit_length()):
        matches_in_round = current_teams // 2
        
        for match_num in range(matches_in_round):
            # Assign teams for first round, None for later rounds
            if round_num == 1:
                team1_id = teams[match_num * 2].team_id if match_num * 2 < len(teams) else None
                team2_id = teams[match_num * 2 + 1].team_id if match_num * 2 + 1 < len(teams) else None
                status = 'Scheduled' if match_num * 2 + 1 < len(teams) else 'Pending'
                
                # Track bye teams
                if match_num * 2 + 1 >= len(teams) and match_num * 2 < len(teams):
                    bye_teams.append(teams[match_num * 2])
            else:
                team1_id = None
                team2_id = None
                status = 'Pending'
                
            match = Match(
                tournament_id=tournament_id,
                stage_type=stage_type,
                round_type='Winners',
                stage_match_number=len(matches) + 1,
                global_match_order=start_order + len(matches),
                team1_id=team1_id,
                team2_id=team2_id,
                match_status=status
            )
            db.session.add(match)
            matches.append(match)
        
        current_teams //= 2
    
    # Generate losers bracket (simplified)
    if len(teams) > 2:
        losers_matches_needed = max(1, (len(teams) - 1) // 2)
        for match_num in range(losers_matches_needed):
            match = Match(
                tournament_id=tournament_id,
                stage_type=stage_type,
                round_type='Losers',
                stage_match_number=len(matches) + 1,
                global_match_order=start_order + len(matches),
                team1_id=None,
                team2_id=None,
                match_status='Pending'
            )
            db.session.add(match)
            matches.append(match)
    
    return matches, bye_teams

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
