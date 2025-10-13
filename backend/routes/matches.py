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
    
    if len(teams) <= 12:
        # Single group stage for <= 12 teams
        group_matches, group_byes = _generate_group_matches(tournament_id, teams, 'Group_A', match_order)
        matches.extend(group_matches)
        all_bye_teams.extend(group_byes)
    else:
        # Multi-stage format for 13+ teams: Group A/B -> Finals
        mid_point = len(teams) // 2
        group_a_teams = teams[:mid_point]
        group_b_teams = teams[mid_point:]
        
        # Generate Group A matches using single-group logic
        group_a_matches, group_a_byes = _generate_group_matches(tournament_id, group_a_teams, 'Group_A', match_order)
        matches.extend(group_a_matches)
        all_bye_teams.extend(group_a_byes)
        match_order += len(group_a_matches)
        
        # Generate Group B matches using single-group logic  
        group_b_matches, group_b_byes = _generate_group_matches(tournament_id, group_b_teams, 'Group_B', match_order)
        matches.extend(group_b_matches)
        all_bye_teams.extend(group_b_byes)
        match_order += len(group_b_matches)
        
        # Fix Group A: Change existing Championship matches to regular matches and add final matches
        group_a_championships = [m for m in group_a_matches if m.round_type == 'Championship']
        for champ_match in group_a_championships:
            champ_match.round_type = 'Winners'  # Change to regular match
        
        # Add Group A final matches: 1 winners final, 2 losers finals (last one Championship)
        # Winners final
        group_a_winners_final = Match(
            tournament_id=tournament_id, stage_type='Group_A', round_type='Winners',
            stage_match_number=len(group_a_matches) + 1, global_match_order=match_order,
            team1_id=None, team2_id=None, match_status='Pending'
        )
        db.session.add(group_a_winners_final)
        matches.append(group_a_winners_final)
        match_order += 1
        
        # Losers semifinal
        group_a_losers_semi = Match(
            tournament_id=tournament_id, stage_type='Group_A', round_type='Losers',
            stage_match_number=len(group_a_matches) + 2, global_match_order=match_order,
            team1_id=None, team2_id=None, match_status='Pending'
        )
        db.session.add(group_a_losers_semi)
        matches.append(group_a_losers_semi)
        match_order += 1
        
        # Losers final (Championship)
        group_a_losers_final = Match(
            tournament_id=tournament_id, stage_type='Group_A', round_type='Championship',
            stage_match_number=len(group_a_matches) + 3, global_match_order=match_order,
            team1_id=None, team2_id=None, match_status='Completed'
        )
        db.session.add(group_a_losers_final)
        matches.append(group_a_losers_final)
        match_order += 1
        
        # Fix Group B: Same process
        group_b_championships = [m for m in group_b_matches if m.round_type == 'Championship']
        for champ_match in group_b_championships:
            champ_match.round_type = 'Winners'
        
        # Add Group B final matches
        group_b_winners_final = Match(
            tournament_id=tournament_id, stage_type='Group_B', round_type='Winners',
            stage_match_number=len(group_b_matches) + 1, global_match_order=match_order,
            team1_id=None, team2_id=None, match_status='Pending'
        )
        db.session.add(group_b_winners_final)
        matches.append(group_b_winners_final)
        match_order += 1
        
        group_b_losers_semi = Match(
            tournament_id=tournament_id, stage_type='Group_B', round_type='Losers',
            stage_match_number=len(group_b_matches) + 2, global_match_order=match_order,
            team1_id=None, team2_id=None, match_status='Pending'
        )
        db.session.add(group_b_losers_semi)
        matches.append(group_b_losers_semi)
        match_order += 1
        
        group_b_losers_final = Match(
            tournament_id=tournament_id, stage_type='Group_B', round_type='Championship',
            stage_match_number=len(group_b_matches) + 3, global_match_order=match_order,
            team1_id=None, team2_id=None, match_status='Completed'
        )
        db.session.add(group_b_losers_final)
        matches.append(group_b_losers_final)
    
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
    
    # Generate losers bracket matches - algorithmic approach for any team count
    losers_matches = []
    if len(teams) >= 4:
        # In double elimination: winners bracket eliminates (n-2) teams to losers bracket
        # Losers bracket must eliminate (n-4) teams, leaving 2 survivors
        teams_to_losers = len(teams) - 2
        teams_to_eliminate = teams_to_losers - 2
        
        # Calculate losers bracket structure algorithmically
        # Need enough matches to eliminate teams_to_eliminate teams
        # Each match eliminates 1 team, so need teams_to_eliminate matches minimum
        # But also need to handle the flow of teams through rounds
        
        # For proper double elimination structure:
        # Losers bracket must eliminate exactly (teams_to_eliminate) teams
        # Each match eliminates 1 team, so need exactly teams_to_eliminate matches
        # The final match winner advances to Losers Championship
        
        losers_matches_needed = teams_to_eliminate
        
        for i in range(losers_matches_needed):
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
        # WB Championship (2 winners) - NOT scoreable, just holds survivors
        wb_championship = Match(
            tournament_id=tournament_id,
            stage_type=stage_type,
            round_type='Championship',
            stage_match_number=len(matches) + 1,
            global_match_order=start_order + len(matches),
            team1_id=None,  # Will be populated by advancement
            team2_id=None,  # Will be populated by advancement
            match_status='Pending',  # Pending until populated, then becomes unscoreable
            winner_advances_to_match_id=None,  # No advancement from group stage
            loser_advances_to_match_id=None
        )
        db.session.add(wb_championship)
        matches.append(wb_championship)
        
        # LB Championship (2 losers) - NOT scoreable, just holds survivors
        lb_championship = Match(
            tournament_id=tournament_id,
            stage_type=stage_type,
            round_type='Championship',
            stage_match_number=len(matches) + 1,
            global_match_order=start_order + len(matches),
            team1_id=None,  # Will be populated by advancement
            team2_id=None,  # Will be populated by advancement
            match_status='Pending',  # Pending until populated, then becomes unscoreable
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
        # First round winners bracket losers go to losers bracket
        first_round_winners = winners_matches[0]
        
        # Pair up first-round losers in losers bracket matches
        for i, winner_match in enumerate(first_round_winners):
            if i < len(losers_matches) * 2:  # Each losers match takes 2 teams
                losers_match_index = i // 2
                winner_match.loser_advances_to_match_id = losers_matches[losers_match_index].match_id
            else:
                # Bye teams go directly to the next losers round match
                if i == len(losers_matches) * 2 and len(losers_matches) > 0:
                    # Place bye team in the match that the first losers match winner advances to
                    next_match_id = losers_matches[0].winner_advances_to_match_id
                    if next_match_id:
                        winner_match.loser_advances_to_match_id = next_match_id
                        # Pre-place the bye team in that match
                        next_match = Match.query.get(next_match_id)
                        if next_match and not next_match.team1_id:
                            # Get the bye team (loser from this match when it happens)
                            # We need to set this up so the bye team gets placed when the match is scored
                            pass  # This will be handled by a different approach
        
        # Handle bye team pre-placement for odd number of first-round matches
        if len(first_round_winners) % 2 == 1:
            # The last team (from the odd match) gets a bye
            bye_match = first_round_winners[-1]
            if bye_match.loser_advances_to_match_id:
                # Pre-place the bye team in the target match
                target_match = Match.query.get(bye_match.loser_advances_to_match_id)
                if target_match:
                    # The bye team will be the loser of this match, so pre-place them
                    # We'll handle this by modifying the scoring logic to place bye teams
                    pass
        
        # Set up losers bracket internal advancement - proper double elimination structure
        if len(losers_matches) > 0:
            # For proper double elimination, losers matches should form a structured elimination tree
            # Early matches eliminate teams, later matches handle survivors + new losers from winners
            
            # Simple chain for now - can be enhanced for more complex structures
            for i in range(len(losers_matches) - 1):
                losers_matches[i].winner_advances_to_match_id = losers_matches[i + 1].match_id
            
            # Last losers match winner advances to Losers Championship
            if len(matches) >= 2:
                losers_matches[-1].winner_advances_to_match_id = matches[-1].match_id
        
        # Set up winners bracket losers feeding into losers bracket - proper pairing
        # In double elimination, teams should be paired for elimination, not distributed
        
        if losers_matches:
            # Collect all winners bracket matches that need losers advancement
            all_wb_matches = []
            for round_matches in winners_matches:
                all_wb_matches.extend(round_matches)
            
            # Pair teams properly: every 2 teams go to same losers match for elimination
            losers_match_idx = 0
            team_count = 0
            
            for match in all_wb_matches:
                if losers_match_idx < len(losers_matches):
                    match.loser_advances_to_match_id = losers_matches[losers_match_idx].match_id
                    team_count += 1
                    
                    # Every 2 teams, move to next losers match (so they face each other)
                    if team_count % 2 == 0:
                        losers_match_idx += 1
    
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

def _generate_multi_group_matches(tournament_id, teams, stage_type, start_order):
    """Generate multi-group matches without Championship matches - stops at 2 survivors"""
    matches = []
    
    if len(teams) < 2:
        return matches
    
    # Find the next power of 2 that can accommodate all teams
    bracket_size = 2
    while bracket_size < len(teams):
        bracket_size *= 2
    
    # Generate winners bracket matches - stop at 2 survivors instead of 4
    winners_matches = []
    current_teams = bracket_size
    round_num = 1
    
    # Generate all winners bracket rounds except the final
    while current_teams > 2:  # Stop when we have 2 teams left (the 2 survivors)
        matches_in_round = current_teams // 2
        for i in range(matches_in_round):
            match = Match(
                tournament_id=tournament_id,
                stage_type=stage_type,
                round_type='Winners',
                stage_match_number=len(matches) + 1,
                global_match_order=start_order + len(matches),
                team1_id=None,
                team2_id=None,
                match_status='Pending' if round_num > 1 else 'Scheduled',
                winner_advances_to_match_id=None,
                loser_advances_to_match_id=None
            )
            db.session.add(match)
            matches.append(match)
            winners_matches.append(match)
        
        current_teams //= 2
        round_num += 1
    
    # Generate losers bracket - eliminate to leave exactly 2 survivors total
    losers_matches = []
    if len(teams) > 2:
        # For multi-group: eliminate enough teams to leave exactly 2 survivors
        # We need to eliminate (len(teams) - 2) teams through losers bracket
        teams_to_eliminate = len(teams) - 2
        
        # Generate losers bracket matches to eliminate the required number of teams
        for i in range(teams_to_eliminate):
            match = Match(
                tournament_id=tournament_id,
                stage_type=stage_type,
                round_type='Losers',
                stage_match_number=len(matches) + 1,
                global_match_order=start_order + len(matches),
                team1_id=None,
                team2_id=None,
                match_status='Pending',
                winner_advances_to_match_id=None,
                loser_advances_to_match_id=None
            )
            db.session.add(match)
            matches.append(match)
            losers_matches.append(match)
    
    return matches
    """Generate multi-group matches by using single-group logic but stopping at 2 survivors"""
    # Use the existing single-group logic but modify stopping condition
    matches = []
    
    # Calculate bracket size (next power of 2)
    bracket_size = 1
    while bracket_size < len(teams):
        bracket_size *= 2
    
    # Generate winners bracket matches - stop at 2 survivors instead of 4
    winners_matches = []
    current_teams = bracket_size
    round_num = 1
    
    while current_teams > 2:  # Stop when 2 teams remain (instead of 4)
        round_matches = []
        for i in range(current_teams // 2):
            team1_id = teams[i * 2].team_id if i * 2 < len(teams) else None
            team2_id = teams[i * 2 + 1].team_id if i * 2 + 1 < len(teams) else None
            status = 'Scheduled' if team1_id and team2_id else 'Pending'
            
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
    
    # Generate losers bracket - eliminate to leave exactly 2 survivors total
    losers_matches = []
    if len(teams) > 2:
        # For multi-group: eliminate enough teams to leave exactly 2 survivors
        teams_to_eliminate = len(teams) - 2
        winners_eliminations = len(teams) // 2 - 1  # Winners bracket eliminates all but 2
        losers_eliminations_needed = teams_to_eliminate - winners_eliminations
        
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
    
    # Generate Championship matches for 2 survivors (1 WB winner, 1 LB winner)
    if len(teams) >= 2:
        # WB Championship (1 winner)
        wb_championship = Match(
            tournament_id=tournament_id,
            stage_type=stage_type,
            round_type='Championship',
            stage_match_number=len(matches) + 1,
            global_match_order=start_order + len(matches),
            team1_id=None,
            team2_id=None,
            match_status='Completed',
            winner_advances_to_match_id=None,
            loser_advances_to_match_id=None
        )
        db.session.add(wb_championship)
        matches.append(wb_championship)
        
        # LB Championship (1 loser survivor)  
        lb_championship = Match(
            tournament_id=tournament_id,
            stage_type=stage_type,
            round_type='Championship',
            stage_match_number=len(matches) + 1,
            global_match_order=start_order + len(matches),
            team1_id=None,
            team2_id=None,
            match_status='Completed',
            winner_advances_to_match_id=None,
            loser_advances_to_match_id=None
        )
        db.session.add(lb_championship)
        matches.append(lb_championship)
        
        # Commit to get match IDs
        db.session.flush()
        
        # Set advancement paths to Championship matches
        if winners_matches and winners_matches[-1]:
            # The final winners bracket match advances winner to WB Championship, loser to LB Championship
            winners_matches[-1][-1].winner_advances_to_match_id = wb_championship.match_id
            winners_matches[-1][-1].loser_advances_to_match_id = lb_championship.match_id
        
        if losers_matches:
            # Final losers bracket match winner goes to LB Championship
            losers_matches[-1].winner_advances_to_match_id = lb_championship.match_id
        
        # Set up losers bracket advancement from winners bracket
        for round_idx, round_matches in enumerate(winners_matches[:-1]):  # All but final round
            for match_idx, match in enumerate(round_matches):
                if match_idx < len(losers_matches):
                    match.loser_advances_to_match_id = losers_matches[match_idx].match_id
    
    return matches

def _generate_group_matches(tournament_id, teams, stage_type, start_order):
    """Generate single group stage double elimination bracket - stops at 4 survivors"""
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
    
    # Prevent scoring of Championship matches in group stage (they hold survivors, not compete)
    if match.round_type == 'Championship' and match.stage_type.startswith('Group'):
        return jsonify({'error': 'Championship matches in group stage cannot be scored - they hold survivors for finals seeding'}), 400
    
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
        if match.team1_score is not None and match.team2_score is not None:
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
