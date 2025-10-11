from flask import Blueprint, jsonify, request
from database import db
from models import RegisteredPlayer

players_bp = Blueprint('players', __name__)

@players_bp.route('/api/players', methods=['GET'])
def get_players():
    players = RegisteredPlayer.query.all()
    return jsonify([{
        'player_id': p.player_id,
        'player_name': p.player_name,
        'nickname': p.nickname,
        'division': p.division,
        'seasonal_points': p.seasonal_points,
        'seasonal_cash': float(p.seasonal_cash)
    } for p in players])

@players_bp.route('/api/players', methods=['POST'])
def create_players():
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    players_data = data if isinstance(data, list) else [data]
    created_players = []
    errors = []
    
    for i, player_data in enumerate(players_data):
        if not player_data.get('player_name'):
            errors.append(f'Player {i+1}: Player name is required')
            continue
        
        division = player_data.get('division', 'Am')
        if division not in ['Pro', 'Am', 'Junior']:
            errors.append(f'Player {i+1}: Division must be Pro, Am, or Junior')
            continue
        
        existing = RegisteredPlayer.query.filter_by(player_name=player_data['player_name']).first()
        if existing:
            errors.append(f'Player {i+1}: Player name "{player_data["player_name"]}" already exists')
            continue
        
        player = RegisteredPlayer(
            player_name=player_data['player_name'],
            nickname=player_data.get('nickname'),
            division=division,
            seasonal_points=0,
            seasonal_cash=0.00
        )
        
        db.session.add(player)
        created_players.append(player)
    
    if errors and not created_players:
        return jsonify({'errors': errors}), 400
    
    db.session.commit()
    
    result = {
        'created': [{
            'player_id': p.player_id,
            'player_name': p.player_name,
            'nickname': p.nickname,
            'division': p.division,
            'seasonal_points': p.seasonal_points,
            'seasonal_cash': float(p.seasonal_cash)
        } for p in created_players]
    }
    
    if errors:
        result['errors'] = errors
    
    return jsonify(result), 201
