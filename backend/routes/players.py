from flask import Blueprint, jsonify, request
from database import db
from models import RegisteredPlayer, TournamentRegistration, Tournament, Team, TeamHistory
from routes.auth import require_auth
import csv
import io

players_bp = Blueprint('players', __name__)

@players_bp.route('/api/players/<int:player_id>', methods=['GET'])
def get_player_detail(player_id):
    player = RegisteredPlayer.query.get(player_id)
    if not player:
        return jsonify({'error': 'Player not found'}), 404
    
    # Get tournament history
    tournaments = db.session.query(Tournament, TournamentRegistration, Team).join(
        TournamentRegistration, Tournament.tournament_id == TournamentRegistration.tournament_id
    ).outerjoin(
        Team, db.and_(Team.tournament_id == Tournament.tournament_id, 
                     db.or_(Team.player1_id == player_id, Team.player2_id == player_id))
    ).filter(TournamentRegistration.player_id == player_id).all()
    
    # Get teammate history with names
    teammates = db.session.query(TeamHistory, RegisteredPlayer).join(
        RegisteredPlayer, TeamHistory.teammate_id == RegisteredPlayer.player_id
    ).filter(TeamHistory.player_id == player_id).all()
    
    return jsonify({
        'player_id': player.player_id,
        'player_name': player.player_name,
        'nickname': player.nickname,
        'division': player.division,
        'seasonal_points': player.seasonal_points,
        'seasonal_cash': float(player.seasonal_cash),
        'tournament_history': [{
            'tournament_id': t[0].tournament_id,
            'tournament_date': t[0].tournament_date.isoformat(),
            'status': t[0].status,
            'bought_ace_pot': t[1].bought_ace_pot,
            'final_place': t[2].final_place if t[2] else None
        } for t in tournaments],
        'teammate_history': [{
            'teammate_id': th[0].teammate_id,
            'teammate_name': th[1].player_name,
            'teammate_nickname': th[1].nickname,
            'times_paired': th[0].times_paired,
            'average_place': float(th[0].average_place) if th[0].average_place else None
        } for th in teammates]
    })

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
@require_auth(['Admin', 'Director'])
def create_players():
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    players_data = data if isinstance(data, list) else [data]
    created_players = []
    errors = []
    
    for i, player_data in enumerate(players_data):
        if not player_data.get('player_name'):
            errors.append(f'Player name is required')
            continue
        
        division = player_data.get('division', 'Am')
        if division not in ['Pro', 'Am', 'Junior']:
            errors.append(f'Division must be Pro, Am, or Junior')
            continue
        
        existing = RegisteredPlayer.query.filter_by(player_name=player_data['player_name']).first()
        if existing:
            errors.append(f'"{player_data["player_name"]}" already exists')
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

@players_bp.route('/api/players/<int:player_id>', methods=['PUT'])
@require_auth(['Admin', 'Director'])
def update_player(player_id):
    player = RegisteredPlayer.query.get(player_id)
    if not player:
        return jsonify({'error': 'Player not found'}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Update allowed fields
    if 'player_name' in data:
        player.player_name = data['player_name']
    if 'nickname' in data:
        player.nickname = data['nickname']
    if 'division' in data:
        player.division = data['division']
    
    try:
        db.session.commit()
        return jsonify({
            'player_id': player.player_id,
            'player_name': player.player_name,
            'nickname': player.nickname,
            'division': player.division,
            'seasonal_points': player.seasonal_points,
            'seasonal_cash': float(player.seasonal_cash)
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@players_bp.route('/api/players/batch-csv', methods=['POST'])
@require_auth(['Admin', 'Director'])
def create_players_csv():
    if 'csv_data' not in request.json:
        return jsonify({'error': 'csv_data field required'}), 400
    
    csv_data = request.json['csv_data']
    reader = csv.DictReader(io.StringIO(csv_data))
    
    print(f"Debug - CSV Headers: {reader.fieldnames}")
    
    players_data = []
    for i, row in enumerate(reader):
        print(f"Debug - Row {i}: {dict(row)}")
        # Handle case-insensitive column lookup
        division = row.get('division', row.get('Division', 'Am')).strip()
        print(f"Debug - Raw division: '{division}'")
        # Normalize division case
        if division.lower() == 'pro':
            division = 'Pro'
        elif division.lower() == 'junior':
            division = 'Junior'
        else:
            division = 'Am'
        print(f"Debug - Normalized division: '{division}'")
            
        players_data.append({
            'player_name': row.get('player_name', '').strip(),
            'nickname': row.get('nickname', '').strip() or None,
            'division': division
        })
    
    # Reuse existing batch creation logic
    created_players = []
    errors = []
    
    for i, player_data in enumerate(players_data):
        if not player_data.get('player_name'):
            errors.append(f'Row {i+1}: Player name is required')
            continue
        
        division = player_data.get('division', 'Am')
        if division not in ['Pro', 'Am', 'Junior']:
            errors.append(f'Row {i+1}: Division must be Pro, Am, or Junior')
            continue
        
        existing = RegisteredPlayer.query.filter_by(player_name=player_data['player_name']).first()
        if existing:
            errors.append(f'Row {i+1}: Player name "{player_data["player_name"]}" already exists')
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
            'division': p.division
        } for p in created_players]
    }
    
    if errors:
        result['errors'] = errors
    
    return jsonify(result), 201
