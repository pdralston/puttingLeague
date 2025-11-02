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
    
    # Auto-advance matches with only one team (bye matches)
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
    
    teams = Team.query.filter_by(tournament_id=tournament_id).all()
    if len(teams) < 4:
        return jsonify({'error': 'Need at least 4 teams'}), 400
    
    # Calculate bracket parameters
    bracket_size = 1 << (len(teams) - 1).bit_length() if len(teams) & (len(teams) - 1) else len(teams)
    wb_rounds = int(math.log2(bracket_size))
    byes_needed = bracket_size - len(teams)
    
    matches = []
    match_id = 1
    
    # Create winners bracket matches
    for round_num in range(wb_rounds):
        matches_in_round = bracket_size >> (round_num + 1)
        for pos in range(matches_in_round):
            matches.append(Match(
                tournament_id=tournament_id, match_id=match_id, stage_type='Group_A',
                round_type='Winners', round_number=round_num, position_in_round=pos,
                stage_match_number=match_id, match_order=match_id, match_status='Pending'
            ))
            match_id += 1
    
    # Create losers bracket matches (only if needed)
    if len(teams) - byes_needed > 1:
        lb_rounds = (wb_rounds - 1) * 2
        for round_num in range(lb_rounds):
            matches_in_round = 1 if round_num == 0 else bracket_size >> ((round_num + 2) // 2 + 1)
            for pos in range(matches_in_round):
                matches.append(Match(
                    tournament_id=tournament_id, match_id=match_id, stage_type='Group_A',
                    round_type='Losers', round_number=round_num, position_in_round=pos,
                    stage_match_number=match_id, match_order=match_id, match_status='Pending'
                ))
                match_id += 1
    
    # Create championship match
    championship = Match(
        tournament_id=tournament_id, match_id=match_id, stage_type='Finals',
        round_type='Championship', round_number=0, position_in_round=0,
        stage_match_number=match_id, match_order=match_id, match_status='Pending'
    )
    matches.append(championship)
    
    # Set all advancement paths in memory
    wb_matches = [m for m in matches if m.round_type == 'Winners']
    lb_matches = [m for m in matches if m.round_type == 'Losers']
    
    # Winners bracket progression
    for match in wb_matches:
        if match.round_number < wb_rounds - 1:
            next_pos = match.position_in_round // 2
            next_match = next((m for m in wb_matches 
                             if m.round_number == match.round_number + 1 
                             and m.position_in_round == next_pos), None)
            if next_match:
                match.winner_advances_to_match_id = next_match.match_id
        else:
            match.winner_advances_to_match_id = championship.match_id
    
    # Losers bracket progression
    for match in lb_matches:
        if match.round_number < len(lb_matches) and match.round_number < (wb_rounds - 1) * 2 - 1:
            next_pos = match.position_in_round // 2
            next_match = next((m for m in lb_matches 
                             if m.round_number == match.round_number + 1 
                             and m.position_in_round == next_pos), None)
            if next_match:
                match.winner_advances_to_match_id = next_match.match_id
        else:
            match.winner_advances_to_match_id = championship.match_id
    
    # Seed teams and handle byes
    first_round = [m for m in wb_matches if m.round_number == 0]
    bye_matches_to_remove = []
    
    for i in range(byes_needed):
        first_round[i].team1_id = teams[i].team_id
        first_round[i].match_status = 'Scheduled'
        # Auto-advance bye teams
        if first_round[i].winner_advances_to_match_id:
            next_match = next((m for m in matches if m.match_id == first_round[i].winner_advances_to_match_id), None)
            if next_match:
                if next_match.team1_id is None:
                    next_match.team1_id = teams[i].team_id
                elif next_match.team2_id is None:
                    next_match.team2_id = teams[i].team_id
                if next_match.team1_id and next_match.team2_id:
                    next_match.match_status = 'Scheduled'
        bye_matches_to_remove.append(first_round[i])
    
    # Seed real matches
    team_idx = byes_needed
    for i in range(byes_needed, len(first_round)):
        if team_idx < len(teams):
            first_round[i].team1_id = teams[team_idx].team_id
            team_idx += 1
        if team_idx < len(teams):
            first_round[i].team2_id = teams[team_idx].team_id
            first_round[i].match_status = 'Scheduled'
            team_idx += 1
    
    # Set losers bracket drops for real matches only
    for match in wb_matches:
        if match.round_number == 0 and match.team2_id is not None:
            lb_match = next((m for m in lb_matches if m.round_number == 0), None)
            if lb_match:
                match.loser_advances_to_match_id = lb_match.match_id
        elif match.round_number > 0:
            lb_round = (match.round_number - 1) * 2 + 1
            lb_match = next((m for m in lb_matches 
                           if m.round_number == lb_round and m.position_in_round == match.position_in_round), None)
            if lb_match:
                match.loser_advances_to_match_id = lb_match.match_id
    
    # Handle losers bracket byes in rounds 0 and 1
    for lb_match in lb_matches:
        if lb_match.round_number in [0, 1]:
            feeding_matches = [m for m in matches if m.winner_advances_to_match_id == lb_match.match_id or m.loser_advances_to_match_id == lb_match.match_id]
            if len(feeding_matches) == 1:
                feeding_matches[0].loser_advances_to_match_id = lb_match.winner_advances_to_match_id
                bye_matches_to_remove.append(lb_match)
    
    # Remove bye matches from the list
    for bye_match in bye_matches_to_remove:
        matches.remove(bye_match)
    
    # Set match_order for all non-Championship matches
    non_championship_matches = [m for m in matches if m.round_type != 'Championship']
    non_championship_matches.sort(key=lambda m: (m.round_number, m.round_type == 'Losers', m.match_id))
    for i, match in enumerate(non_championship_matches, 1):
        match.match_order = i
    
    # Single database transaction
    db.session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
    db.session.add_all(matches)
    db.session.commit()
    db.session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    
    return jsonify({'tournament_id': tournament_id, 'matches_created': len(matches)}), 201
    

# Removed old bracket generation functions
  

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

def _advance_team_to_match(team_id, tournament_id, target_match_id):
    """Advance a team to the next match"""
    target_match = Match.query.filter_by(tournament_id=tournament_id, match_id=target_match_id).first()
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
    """Auto-advance teams in bye matches (matches with only one team that won't get a second team)"""
    matches = Match.query.filter_by(tournament_id=tournament_id).all()
    
    for match in matches:
        # Skip if match is already completed or in progress
        if match.match_status not in ['Pending']:
            continue
            
        # Check if this is a bye match (has one team but no second team will come)
        if match.team1_id and not match.team2_id:
            # Count how many matches feed into this match
            feeding_matches = [m for m in matches if 
                             m.winner_advances_to_match_id == match.match_id or 
                             m.loser_advances_to_match_id == match.match_id]
            
            # If only one match feeds into this one and it's completed, this is a bye
            completed_feeding = [m for m in feeding_matches if m.match_status == 'Completed']
            
            if len(feeding_matches) == 1 and len(completed_feeding) == 1:
                # This is a true bye - auto-advance
                match.team1_score = 1
                match.team2_score = 0
                match.match_status = 'Completed'
                
                # Advance the team to the next match
                if match.winner_advances_to_match_id:
                    next_match = next((m for m in matches if m.match_id == match.winner_advances_to_match_id), None)
                    if next_match:
                        if not next_match.team1_id:
                            next_match.team1_id = match.team1_id
                        elif not next_match.team2_id:
                            next_match.team2_id = match.team1_id
                        
                        # Update status to Scheduled if both teams are now assigned
                        if next_match.team1_id and next_match.team2_id and next_match.match_status == 'Pending':
                            next_match.match_status = 'Scheduled'
            elif len(feeding_matches) == 0:
                # This match has a seeded team but no feeding matches - it's waiting for another team
                # Check if it should be scheduled (if it will get a second team from another completed match)
                pass  # Keep as Pending until second team arrives

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
    """Count matches won by player's team (excluding byes)"""
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
            # Skip bye matches (only one team)
            if match.team2_id is None:
                continue
                
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