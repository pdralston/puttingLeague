from flask import Blueprint, jsonify, request
from datetime import datetime
import random
from database import db
from models import Tournament, TournamentRegistration, RegisteredPlayer, AcePot, Team, Match

tournaments_bp = Blueprint('tournaments', __name__)

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
        tournaments = Tournament.query.order_by(Tournament.tournament_date.desc()).all()
        return jsonify([{
            'tournament_id': t.tournament_id,
            'tournament_date': t.tournament_date.isoformat(),
            'status': t.status,
            'total_teams': t.total_teams,
            'ace_pot_payout': float(t.ace_pot_payout) if t.ace_pot_payout else 0.00
        } for t in tournaments])

@tournaments_bp.route('/api/tournaments', methods=['POST'])
def create_tournament():
    data = request.get_json()
    
    if not data or not data.get('tournament_date'):
        return jsonify({'error': 'Tournament date is required'}), 400
    
    try:
        tournament_date = datetime.strptime(data['tournament_date'], '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
    
    tournament = Tournament(
        tournament_date=tournament_date,
        status='Scheduled',
        total_teams=0,
        ace_pot_payout=0.00
    )
    
    db.session.add(tournament)
    db.session.commit()
    
    return jsonify({
        'tournament_id': tournament.tournament_id,
        'tournament_date': tournament.tournament_date.isoformat(),
        'status': tournament.status,
        'total_teams': tournament.total_teams,
        'ace_pot_payout': float(tournament.ace_pot_payout)
    }), 201

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
    registered_players = []
    ace_pot_buyins = 0
    errors = []
    
    for i, reg in enumerate(registrations):
        if 'player_name' in reg:
            division = reg.get('division', 'Am')
            if division not in ['Pro', 'Am', 'Junior']:
                errors.append(f'Registration {i+1}: Division must be Pro, Am, or Junior')
                continue
            
            existing = RegisteredPlayer.query.filter_by(player_name=reg['player_name']).first()
            if existing:
                player = existing
            else:
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
        
        elif 'player_id' in reg:
            player = RegisteredPlayer.query.get(reg['player_id'])
            if not player:
                errors.append(f'Registration {i+1}: Player ID {reg["player_id"]} not found')
                continue
        else:
            errors.append(f'Registration {i+1}: Must provide either player_id or player_name')
            continue
        
        existing_reg = TournamentRegistration.query.filter_by(
            tournament_id=tournament_id, 
            player_id=player.player_id
        ).first()
        
        if existing_reg:
            errors.append(f'Registration {i+1}: Player "{player.player_name}" already registered')
            continue
        
        registration = TournamentRegistration(
            tournament_id=tournament_id,
            player_id=player.player_id,
            bought_ace_pot=reg.get('bought_ace_pot', False)
        )
        
        db.session.add(registration)
        registered_players.append(player)
        
        if reg.get('bought_ace_pot', False):
            ace_pot_buyins += 1
    
    if errors and not registered_players:
        return jsonify({'errors': errors}), 400
    
    if ace_pot_buyins > 0:
        ace_pot_amount = ace_pot_buyins * 1.00
        ace_pot_entry = AcePot(
            tournament_id=tournament_id,
            date=tournament.tournament_date,
            description=f'Tournament {tournament.tournament_date}: {ace_pot_buyins} buy-ins',
            amount=ace_pot_amount
        )
        db.session.add(ace_pot_entry)
    
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
    
    if errors:
        result['errors'] = errors
    
    return jsonify(result), 201

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
            'seed_number': team.seed_number
        })
    
    return jsonify(result)

@tournaments_bp.route('/api/tournaments/<int:tournament_id>/generate-teams', methods=['POST'])
def generate_teams(tournament_id):
    if tournament_id <= 0:
        return jsonify({'error': 'Invalid tournament ID'}), 400
    
    tournament = Tournament.query.get(tournament_id)
    if not tournament:
        return jsonify({'error': 'Tournament not found'}), 404
    
    registrations = db.session.query(TournamentRegistration, RegisteredPlayer).join(
        RegisteredPlayer, TournamentRegistration.player_id == RegisteredPlayer.player_id
    ).filter(TournamentRegistration.tournament_id == tournament_id).all()
    
    if not registrations:
        return jsonify({'error': 'No players registered for this tournament'}), 400
    
    players = [reg[1] for reg in registrations]
    num_players = len(players)
    
    # Clear existing matches and teams for this tournament
    Match.query.filter_by(tournament_id=tournament_id).delete()  # Delete matches first
    Team.query.filter_by(tournament_id=tournament_id).delete()   # Then delete teams
    
    player_list = players.copy()
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
            tournament_id=tournament_id,
            player1_id=player_one.player_id,
            player2_id=player_two.player_id,
            is_ghost_team=False,
            seed_number=len(teams) + 1
        )
        db.session.add(team)
        teams.append(team)
    
    if len(player_list) > 0:
        team = Team(
            tournament_id=tournament_id,
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
        'tournament_id': tournament_id,
        'total_players': num_players,
        'total_teams': len(teams),
        'has_ghost_team': any(t.is_ghost_team for t in teams),
        'teams': [{
            'team_id': t.team_id,
            'player1_id': t.player1_id,
            'player2_id': t.player2_id,
            'is_ghost_team': t.is_ghost_team,
            'seed_number': t.seed_number
        } for t in teams]
    }), 201
