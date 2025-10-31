from flask import Blueprint, jsonify, request
from datetime import datetime
import random
from database import db
from models import Tournament, TournamentRegistration, RegisteredPlayer, AcePot, Team, Match

tournaments_bp = Blueprint('tournaments', __name__)

def _register_players_helper(tournament_id, tournament_date, players_data):
    """Helper function to register players and handle ace pot"""
    registered_players = []
    ace_pot_buyins = 0
    
    for player_data in players_data:
        if isinstance(player_data, dict):
            player_id = player_data.get('player_id')
            bought_ace_pot = player_data.get('bought_ace_pot', False)
        else:
            player_id = player_data
            bought_ace_pot = False
            
        player = RegisteredPlayer.query.get(player_id)
        if not player:
            raise ValueError(f'Player ID {player_id} not found')
        
        # Check if already registered
        existing_reg = TournamentRegistration.query.filter_by(
            tournament_id=tournament_id, 
            player_id=player_id
        ).first()
        
        if not existing_reg:
            registration = TournamentRegistration(
                tournament_id=tournament_id,
                player_id=player_id,
                bought_ace_pot=bought_ace_pot
            )
            db.session.add(registration)
            registered_players.append(player)
            
            if bought_ace_pot:
                ace_pot_buyins += 1
    
    # Add ace pot entry if there are buy-ins
    if ace_pot_buyins > 0:
        ace_pot_amount = ace_pot_buyins * 1.00
        ace_pot_entry = AcePot(
            tournament_id=tournament_id,
            date=tournament_date,
            description=f'Tournament {tournament_date}: {ace_pot_buyins} buy-ins',
            amount=ace_pot_amount
        )
        db.session.add(ace_pot_entry)
    
    return registered_players, ace_pot_buyins

@tournaments_bp.route('/api/tournaments', methods=['GET'])
def get_tournaments():
    date_param = request.args.get('date')
    id_param = request.args.get('id')
    
    if date_param or id_param:
        if date_param:
            try:
                tournament_date = datetime.strptime(date_param, '%Y-%m-%d').date()
                tournament = Tournament.query.filter_by(tournament_date=tournament_date).first()
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        else:
            try:
                tournament_id = int(id_param)
                if tournament_id <= 0:
                    return jsonify({'error': 'Invalid tournament ID'}), 400
                tournament = Tournament.query.get(tournament_id)
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid tournament ID'}), 400
        
        if not tournament:
            return jsonify({'error': 'Tournament not found'}), 404
        
        registrations = db.session.query(TournamentRegistration, RegisteredPlayer).join(
            RegisteredPlayer, TournamentRegistration.player_id == RegisteredPlayer.player_id
        ).filter(TournamentRegistration.tournament_id == tournament.tournament_id).all()
        
        teams = Team.query.filter_by(tournament_id=tournament.tournament_id).all()
        
        return jsonify({
            'tournament_id': tournament.tournament_id,
            'tournament_date': tournament.tournament_date.isoformat(),
            'status': tournament.status,
            'total_teams': tournament.total_teams,
            'ace_pot_payout': float(tournament.ace_pot_payout),
            'registered_players': [{
                'player_id': reg[1].player_id,
                'player_name': reg[1].player_name,
                'nickname': reg[1].nickname,
                'division': reg[1].division,
                'bought_ace_pot': reg[0].bought_ace_pot
            } for reg in registrations],
            'teams': [{
                'team_id': t.team_id,
                'player1_id': t.player1_id,
                'player2_id': t.player2_id,
                'is_ghost_team': t.is_ghost_team,
                'seed_number': t.seed_number
            } for t in teams]
        })
    else:
        try:
            tournaments = Tournament.query.order_by(Tournament.tournament_id.desc()).all()
            return jsonify([{
                'tournament_id': t.tournament_id,
                'tournament_date': t.tournament_date.isoformat() if t.tournament_date else None,
                'status': t.status,
                'total_teams': t.total_teams,
                'ace_pot_payout': float(t.ace_pot_payout) if t.ace_pot_payout else 0.00
            } for t in tournaments])
        except Exception as e:
            print(f"Error fetching tournaments: {e}")
            return jsonify({'error': 'Failed to fetch tournaments'}), 500

@tournaments_bp.route('/api/tournaments', methods=['POST'])
def create_tournament():
    data = request.get_json()
    
    if not data or not data.get('tournament_date'):
        return jsonify({'error': 'Tournament date is required'}), 400
    
    try:
        tournament_date = datetime.strptime(data['tournament_date'], '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
    
    players = data.get('players', [])
    if len(players) < 2:
        return jsonify({'error': 'At least 2 players required to create tournament'}), 400
    
    try:
        # Create tournament
        tournament = Tournament(
            tournament_date=tournament_date,
            status='Scheduled',
            total_teams=0,
            ace_pot_payout=0.00
        )
        
        db.session.add(tournament)
        db.session.flush()  # Get tournament ID
        
        # Register players using helper
        registered_players, ace_pot_buyins = _register_players_helper(
            tournament.tournament_id, tournament_date, players
        )
        
        # Generate teams
        player_list = registered_players.copy()
        teams = []
        
        while len(player_list) >= 2:
            player_one = player_list.pop()
            n = len(player_list)
            index = random.randint(0, n-1)
            
            if index >= n:
                player_two = player_list.pop()
            else:
                player_two = player_list[index]
                player_list[index] = player_list[n-1]
                player_list.pop()
            
            team = Team(
                tournament_id=tournament.tournament_id,
                player1_id=player_one.player_id,
                player2_id=player_two.player_id,
                is_ghost_team=False,
                seed_number=len(teams) + 1
            )
            db.session.add(team)
            teams.append(team)
        
        # Handle odd player (ghost team)
        if len(player_list) > 0:
            team = Team(
                tournament_id=tournament.tournament_id,
                player1_id=player_list.pop().player_id,
                player2_id=None,
                is_ghost_team=True,
                seed_number=len(teams) + 1
            )
            db.session.add(team)
            teams.append(team)
        
        tournament.total_teams = len(teams)
        db.session.commit()
        
        return jsonify({
            'tournament_id': tournament.tournament_id,
            'tournament_date': tournament.tournament_date.isoformat(),
            'status': tournament.status,
            'total_teams': tournament.total_teams,
            'total_players': len(registered_players),
            'teams_generated': len(teams),
            'ace_pot_buyins': ace_pot_buyins,
            'ace_pot_amount': ace_pot_buyins * 1.00
        }), 201
        
    except ValueError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to create tournament'}), 500

@tournaments_bp.route('/api/tournaments/<int:tournament_id>/register-players', methods=['POST'])
def register_players_for_tournament(tournament_id):
    if tournament_id <= 0:
        return jsonify({'error': 'Invalid tournament ID'}), 400
        
    data = request.get_json()
    
    if not data or not data.get('registrations'):
        return jsonify({'error': 'Registrations list is required'}), 400
    
    tournament = Tournament.query.get(tournament_id)
    if not tournament:
        return jsonify({'error': 'Tournament not found'}), 404
    
    registrations = data['registrations']
    created_players = []
    errors = []
    
    # Create new players if needed
    for i, reg in enumerate(registrations):
        if 'player_name' in reg:
            division = reg.get('division', 'Am')
            if division not in ['Pro', 'Am', 'Junior']:
                errors.append(f'Registration {i+1}: Division must be Pro, Am, or Junior')
                continue
            
            existing = RegisteredPlayer.query.filter_by(player_name=reg['player_name']).first()
            if not existing:
                player = RegisteredPlayer(
                    player_name=reg['player_name'],
                    nickname=reg.get('nickname'),
                    division=division,
                    seasonal_points=0,
                    seasonal_cash=0.00
                )
                db.session.add(player)
                db.session.flush()
                created_players.append(player)
                reg['player_id'] = player.player_id
    
    if errors:
        return jsonify({'errors': errors}), 400
    
    # Convert registrations to players format for helper
    players_data = []
    for reg in registrations:
        if 'player_id' in reg:
            players_data.append({
                'player_id': reg['player_id'],
                'bought_ace_pot': reg.get('bought_ace_pot', False)
            })
    
    try:
        registered_players, ace_pot_buyins = _register_players_helper(
            tournament_id, tournament.tournament_date, players_data
        )
        
        db.session.commit()
        
        result = {
            'tournament_id': tournament_id,
            'registered_players': len(registered_players),
            'ace_pot_buyins': ace_pot_buyins,
            'ace_pot_amount': ace_pot_buyins * 1.00,
            'players': [{
                'player_id': p.player_id,
                'player_name': p.player_name,
                'nickname': p.nickname,
                'division': p.division
            } for p in registered_players]
        }
        
        if created_players:
            result['new_players_created'] = len(created_players)
        
        return jsonify(result), 201
        
    except ValueError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to register players'}), 500

@tournaments_bp.route('/api/tournaments/<int:tournament_id>/matches', methods=['GET'])
def get_tournament_matches(tournament_id):
    matches = Match.query.filter_by(tournament_id=tournament_id).order_by(Match.match_order).all()
    return jsonify([{
        'match_id': m.match_id,
        'match_order': m.match_order,
        'round_type': m.round_type,
        'round_number': m.round_number,
        'team1_id': m.team1_id,
        'team2_id': m.team2_id,
        'team1_score': m.team1_score,
        'team2_score': m.team2_score,
        'match_status': m.match_status,
        'station_assignment': m.station_assignment,
        'winner_advances_to_match_id': m.winner_advances_to_match_id,
        'loser_advances_to_match_id': m.loser_advances_to_match_id
    } for m in matches])

@tournaments_bp.route('/api/tournaments/<int:tournament_id>/teams', methods=['GET'])
def get_tournament_teams(tournament_id):
    teams = Team.query.filter_by(tournament_id=tournament_id).all()
    result = []
    for team in teams:
        player1 = RegisteredPlayer.query.get(team.player1_id)
        player2 = RegisteredPlayer.query.get(team.player2_id) if team.player2_id else None
        
        result.append({
            'team_id': team.team_id,
            'player1_id': team.player1_id,
            'player1_name': player1.player_name if player1 else None,
            'player2_id': team.player2_id,
            'player2_name': player2.player_name if player2 else None,
            'is_ghost_team': team.is_ghost_team,
            'seed_number': team.seed_number,
            'final_place': team.final_place
        })
    
    return jsonify(result)

@tournaments_bp.route('/api/tournaments/<int:tournament_id>/status', methods=['PUT'])
def update_tournament_status(tournament_id):
    data = request.get_json()
    
    if not data or 'status' not in data:
        return jsonify({'error': 'Status is required'}), 400
    
    new_status = data['status']
    if new_status not in ['Scheduled', 'In_Progress', 'Completed']:
        return jsonify({'error': 'Invalid status'}), 400
    
    tournament = Tournament.query.get(tournament_id)
    if not tournament:
        return jsonify({'error': 'Tournament not found'}), 404
    
    tournament.status = new_status
    db.session.commit()
    
    return jsonify({
        'tournament_id': tournament_id,
        'status': tournament.status
    })

@tournaments_bp.route('/api/tournaments/<int:tournament_id>', methods=['DELETE'])
def delete_tournament(tournament_id):
    try:
        # Clean up teammate history and seasonal points before deleting
        tournament = Tournament.query.get(tournament_id)
        if tournament and tournament.status == 'Completed':
            _cleanup_teammate_history(tournament_id)
            _adjust_seasonal_points(tournament_id, reverse=True)
        
        # Delete in dependency order
        Match.query.filter_by(tournament_id=tournament_id).delete()
        Team.query.filter_by(tournament_id=tournament_id).delete()
        TournamentRegistration.query.filter_by(tournament_id=tournament_id).delete()
        AcePot.query.filter_by(tournament_id=tournament_id).delete()
        
        tournament = Tournament.query.get(tournament_id)
        if tournament:
            db.session.delete(tournament)
            db.session.commit()
            return jsonify({'message': 'Tournament deleted successfully'})
        else:
            return jsonify({'error': 'Tournament not found'}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

def _cleanup_teammate_history(tournament_id):
    """Remove teammate history entries for deleted tournament"""
    from models import Team, TeamHistory
    
    teams = Team.query.filter_by(tournament_id=tournament_id).all()
    
    for team in teams:
        if not team.is_ghost_team and team.player2_id:
            # Decrement history for both players
            for player_id, teammate_id in [(team.player1_id, team.player2_id), (team.player2_id, team.player1_id)]:
                history = TeamHistory.query.filter_by(player_id=player_id, teammate_id=teammate_id).first()
                
                if history:
                    history.times_paired -= 1
                    if history.times_paired <= 0:
                        db.session.delete(history)

def _adjust_seasonal_points(tournament_id, reverse=False):
    """Adjust seasonal points for tournament (add or subtract)"""
    from models import RegisteredPlayer, TournamentRegistration, Team, Match
    
    registrations = TournamentRegistration.query.filter_by(tournament_id=tournament_id).all()
    
    for reg in registrations:
        player = RegisteredPlayer.query.get(reg.player_id)
        if player:
            # Calculate same points as when tournament completed
            participation_points = 1
            match_wins = _count_match_wins_for_deletion(tournament_id, reg.player_id)
            top_4_bonus = 2 if _is_top_4_finish_for_deletion(tournament_id, reg.player_id) else 0
            undefeated_bonus = 3 if _is_undefeated_for_deletion(tournament_id, reg.player_id) else 0
            
            total_points = participation_points + match_wins + top_4_bonus + undefeated_bonus
            
            if reverse:
                player.seasonal_points -= total_points
            else:
                player.seasonal_points += total_points

def _count_match_wins_for_deletion(tournament_id, player_id):
    """Count matches won by player's team (for deletion)"""
    from models import Team, Match
    
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

def _is_top_4_finish_for_deletion(tournament_id, player_id):
    """Check if player finished in top 4 (for deletion)"""
    from models import Team
    
    team = Team.query.filter_by(tournament_id=tournament_id).filter(
        db.or_(Team.player1_id == player_id, Team.player2_id == player_id)
    ).first()
    
    return team and team.final_place and team.final_place <= 4

def _is_undefeated_for_deletion(tournament_id, player_id):
    """Check if player's team went undefeated (for deletion)"""
    from models import Team, Match
    
    teams = Team.query.filter_by(tournament_id=tournament_id).filter(
        db.or_(Team.player1_id == player_id, Team.player2_id == player_id)
    ).all()
    
    for team in teams:
        matches = Match.query.filter_by(tournament_id=tournament_id).filter(
            db.or_(Match.team1_id == team.team_id, Match.team2_id == team.team_id)
        ).filter(Match.match_status == 'Completed').all()
        
        for match in matches:
            if ((match.team1_id == team.team_id and match.team1_score < match.team2_score) or
                (match.team2_id == team.team_id and match.team2_score < match.team1_score)):
                return False
    
    return True
