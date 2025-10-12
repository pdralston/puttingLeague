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
    
    # Clear existing matches - first clear foreign key references
    existing_matches = Match.query.filter_by(tournament_id=tournament_id).all()
    for match in existing_matches:
        match.winner_advances_to_match_id = None
        match.loser_advances_to_match_id = None
    db.session.commit()
    Match.query.filter_by(tournament_id=tournament_id).delete()
    
    matches = []
    match_order = 1
    all_bye_teams = []
    
    if len(teams) < 12:
        # Single group stage for < 12 teams (no finals bracket yet)
        group_matches, group_byes = _generate_group_matches(tournament_id, teams, 'Group_A', match_order)
        matches.extend(group_matches)
        all_bye_teams.extend(group_byes)
    else:
        # Multi-stage format for 12+ teams: Group A/B -> Finals
        mid_point = len(teams) // 2
        group_a_teams = teams[:mid_point]
        group_b_teams = teams[mid_point:]
        
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
        'format': 'group_stage',
        'bye_teams': [{
            'team_id': t.team_id,
            'stage_type': 'Group_A' if t in group_a_teams else 'Group_B',
            'round': 1
        } for t in all_bye_teams] if len(teams) >= 12 else [],
        'matches': [{
            'global_match_order': m.global_match_order,
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

def _generate_single_stage_matches(tournament_id, teams, start_order, stage_type='Finals'):
    """Generate group stage double elimination bracket - stops at 4 survivors"""
    matches = []
    
    if len(teams) < 2:
        return matches
    
    # Calculate bracket size - next power of 2
    bracket_size = 1
    while bracket_size < len(teams):
        bracket_size *= 2
    
    # Generate winners bracket matches - stop before finals to leave 4 survivors
    winners_matches = []
    current_teams = bracket_size
    round_num = 1
    
    # Stop when we would have 2 teams left (semifinals), not 1 team (finals)
    while current_teams > 2:
        round_matches = []
        matches_in_round = current_teams // 2
        
        for match_num in range(matches_in_round):
            if round_num == 1:
                # First round - assign actual teams
                team1_id = teams[match_num * 2].team_id if match_num * 2 < len(teams) else None
                team2_id = teams[match_num * 2 + 1].team_id if match_num * 2 + 1 < len(teams) else None
                status = 'Scheduled' if team1_id and team2_id else 'Scheduled'
            else:
                # Later rounds - placeholders
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
            round_matches.append(match)
        
        winners_matches.append(round_matches)
        current_teams //= 2
        round_num += 1
    
    # Generate losers bracket matches - only if we need to eliminate more teams
    losers_matches = []
    if len(teams) > 4:  # Only generate losers matches if we have more than 4 teams
        # For group stage: eliminate enough teams to leave exactly 4 survivors
        winners_survivors = len(teams) // 2  # Winners from semifinals
        losers_survivors = 4 - winners_survivors  # Remaining survivors from losers bracket
        losers_eliminations_needed = (len(teams) // 2) - losers_survivors  # Teams to eliminate in losers bracket
        
        for i in range(max(0, losers_eliminations_needed)):
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
            losers_matches.append(match)
    
    # Generate group stage ending Championship matches (4 survivors)
    if len(teams) >= 4:
        # WB Championship (2 winners)
        wb_championship = Match(
            tournament_id=tournament_id,
            stage_type=stage_type,
            round_type='Championship',
            stage_match_number=len(matches) + 1,
            global_match_order=start_order + len(matches),
            team1_id=None,  # Will be populated by advancement
            team2_id=None,  # Will be populated by advancement
            match_status='Completed',  # Auto-completed, no scoring
            winner_advances_to_match_id=None,  # No advancement from group stage
            loser_advances_to_match_id=None
        )
        db.session.add(wb_championship)
        matches.append(wb_championship)
        
        # LB Championship (2 losers)  
        lb_championship = Match(
            tournament_id=tournament_id,
            stage_type=stage_type,
            round_type='Championship',
            stage_match_number=len(matches) + 1,
            global_match_order=start_order + len(matches),
            team1_id=None,  # Will be populated by advancement
            team2_id=None,  # Will be populated by advancement
            match_status='Completed',  # Auto-completed, no scoring
            winner_advances_to_match_id=None,  # No advancement from group stage
            loser_advances_to_match_id=None
        )
        db.session.add(lb_championship)
        matches.append(lb_championship)
        
        # Commit to get match IDs
        db.session.flush()
        
        # Update winners bracket final match to advance to WB Championship
        if winners_matches and winners_matches[-1]:
            winners_matches[-1][-1].winner_advances_to_match_id = wb_championship.match_id
            winners_matches[-1][-1].loser_advances_to_match_id = lb_championship.match_id
        
        # Update losers bracket final match to advance to LB Championship  
        if losers_matches:
            losers_matches[-1].winner_advances_to_match_id = lb_championship.match_id
        
        # For 4-team tournaments, set direct advancement from first round
        if len(teams) == 4 and len(winners_matches) > 0 and len(winners_matches[0]) >= 2:
            winners_matches[0][0].winner_advances_to_match_id = wb_championship.match_id
            winners_matches[0][0].loser_advances_to_match_id = lb_championship.match_id
            winners_matches[0][1].winner_advances_to_match_id = wb_championship.match_id  
            winners_matches[0][1].loser_advances_to_match_id = lb_championship.match_id
    
    # Flush to get match IDs
    db.session.flush()
    
    # Set winners bracket advancement
    for round_idx in range(len(winners_matches) - 1):
        for match_idx, match in enumerate(winners_matches[round_idx]):
            next_match_idx = match_idx // 2
            if next_match_idx < len(winners_matches[round_idx + 1]):
                match.winner_advances_to_match_id = winners_matches[round_idx + 1][next_match_idx].match_id
    
    # Set losers bracket advancement
    if losers_matches and winners_matches:
        # First round winners bracket losers go to first losers matches
        first_round_winners = winners_matches[0]
        for i, winner_match in enumerate(first_round_winners):
            if i < len(losers_matches) and winner_match.team1_id and winner_match.team2_id:
                winner_match.loser_advances_to_match_id = losers_matches[i].match_id
        
        # Set up internal losers bracket advancement
        for i in range(len(losers_matches) - 1):
            losers_matches[i].winner_advances_to_match_id = losers_matches[i + 1].match_id
        
        # Later winners bracket losers feed into specific losers bracket positions
        losers_idx = len(first_round_winners)
        for round_idx in range(1, len(winners_matches)):  # Include all rounds
            for winner_match in winners_matches[round_idx]:
                if losers_idx < len(losers_matches):
                    winner_match.loser_advances_to_match_id = losers_matches[losers_idx].match_id
                    losers_idx += 1
    
    return matches

@matches_bp.route('/api/tournaments/<int:tournament_id>/generate-finals', methods=['POST'])
def generate_finals(tournament_id):
    if tournament_id <= 0:
        return jsonify({'error': 'Invalid tournament ID'}), 400
    
    # Check if finals already exist
    existing_finals = Match.query.filter_by(tournament_id=tournament_id, stage_type='Finals').first()
    if existing_finals:
        return jsonify({'error': 'Finals bracket already exists'}), 400
    
    # Get group stage Championship matches (the 4 survivors)
    championship_matches = Match.query.filter_by(
        tournament_id=tournament_id, 
        round_type='Championship'
    ).filter(Match.stage_type.in_(['Group_A', 'Group_B'])).all()
    
    if len(championship_matches) != 2:
        return jsonify({'error': f'Expected 2 Championship matches, found {len(championship_matches)}. Complete group stage first.'}), 400
    
    # Extract the 4 survivors from Championship matches
    survivors = []
    for match in championship_matches:
        if match.team1_id and match.team2_id:
            # Determine if this is WB or LB Championship based on advancement pattern
            # WB Championship has teams with 0 losses, LB Championship has teams with 1 loss
            # We can check by looking at the source matches that advanced to this championship
            source_matches = Match.query.filter(
                (Match.winner_advances_to_match_id == match.match_id) |
                (Match.loser_advances_to_match_id == match.match_id)
            ).all()
            
            # If teams advanced as winners, they have 0 losses (WB Championship)
            # If teams advanced as losers, they have 1 loss (LB Championship)
            is_wb_championship = any(m.winner_advances_to_match_id == match.match_id for m in source_matches)
            losses = 0 if is_wb_championship else 1
            
            survivors.append({'team_id': match.team1_id, 'losses': losses})
            survivors.append({'team_id': match.team2_id, 'losses': losses})
    
    if len(survivors) != 4:
        return jsonify({'error': f'Expected 4 survivors, found {len(survivors)}'}), 400
    
    # Create finals bracket
    finals_matches = _create_finals_bracket(tournament_id, survivors)
    
    # Save matches to database
    for match in finals_matches:
        db.session.add(match)
    
    db.session.commit()
    
    return jsonify({
        'message': 'Finals bracket generated successfully',
        'matches_created': len(finals_matches),
        'survivors': survivors
    }), 201

def _create_finals_bracket(tournament_id, survivors):
    """Create the 5-match finals bracket structure"""
    matches = []
    base_order = 1000  # Start finals matches at high order
    
    # Create finals matches with predetermined structure
    finals_structure = [
        {'stage_match_number': 1, 'round_type': 'Winners', 'name': 'WB Final'},
        {'stage_match_number': 2, 'round_type': 'Losers', 'name': 'LB Semifinal'},
        {'stage_match_number': 3, 'round_type': 'Losers', 'name': 'LB Final'},
        {'stage_match_number': 4, 'round_type': 'Championship', 'name': 'Championship'},
        {'stage_match_number': 5, 'round_type': 'Championship', 'name': 'Championship Game 2'}
    ]
    
    # Create match objects
    for i, structure in enumerate(finals_structure):
        match = Match(
            tournament_id=tournament_id,
            stage_type='Finals',
            round_type=structure['round_type'],
            stage_match_number=structure['stage_match_number'],
            global_match_order=base_order + i,
            match_status='Scheduled'
        )
        
        # Seed initial matches
        if structure['stage_match_number'] == 1:  # WB Final
            winners = [s for s in survivors if s['losses'] == 0]
            if len(winners) >= 2:
                match.team1_id = winners[0]['team_id']
                match.team2_id = winners[1]['team_id']
        elif structure['stage_match_number'] == 2:  # LB Semifinal
            losers = [s for s in survivors if s['losses'] == 1]
            if len(losers) >= 2:
                match.team1_id = losers[0]['team_id']
                match.team2_id = losers[1]['team_id']
        
        matches.append(match)
    
    # Set advancement paths
    matches[0].winner_advances_to_match_id = matches[3].match_id  # WB Final winner to Championship
    matches[0].loser_advances_to_match_id = matches[2].match_id   # WB Final loser to LB Final
    matches[1].winner_advances_to_match_id = matches[2].match_id  # LB Semifinal winner to LB Final
    matches[2].winner_advances_to_match_id = matches[3].match_id  # LB Final winner to Championship
    matches[3].loser_advances_to_match_id = matches[4].match_id   # Championship loser to Game 2
    
    return matches

def _generate_group_matches(tournament_id, teams, stage_type, start_order):
    """Generate group stage double elimination bracket"""
    matches = _generate_single_stage_matches(tournament_id, teams, start_order, stage_type)
    return matches, []  # Return empty bye_teams list for now

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
