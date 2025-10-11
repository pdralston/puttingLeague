from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import os
from datetime import datetime
from database import db

load_dotenv()
app = Flask(__name__)
CORS(app)

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL') or \
    f"mysql+pymysql://{os.environ.get('DB_USER', 'root')}:" \
    f"{os.environ.get('DB_PASSWORD', 'password')}@" \
    f"{os.environ.get('DB_HOST', 'localhost')}:" \
    f"{os.environ.get('DB_PORT', '3306')}/" \
    f"{os.environ.get('DB_NAME', 'dgputt')}"

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

@app.route('/')
def health_check():
    return jsonify({"status": "DG Putt API is running", "timestamp": datetime.now().isoformat()})

# Import models after db initialization
from models import RegisteredPlayer, Tournament

@app.route('/api/players', methods=['GET'])
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

@app.route('/api/players', methods=['POST'])
def create_players():
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Handle both single player and bulk registration
    players_data = data if isinstance(data, list) else [data]
    created_players = []
    errors = []
    
    for i, player_data in enumerate(players_data):
        # Validation
        if not player_data.get('player_name'):
            errors.append(f'Player {i+1}: Player name is required')
            continue
        
        division = player_data.get('division', 'Am')
        if division not in ['Pro', 'Am', 'Junior']:
            errors.append(f'Player {i+1}: Division must be Pro, Am, or Junior')
            continue
        
        # Check for duplicate name
        existing = RegisteredPlayer.query.filter_by(player_name=player_data['player_name']).first()
        if existing:
            errors.append(f'Player {i+1}: Player name "{player_data["player_name"]}" already exists')
            continue
        
        # Create player
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

@app.route('/api/tournaments', methods=['GET'])
def get_tournaments():
    tournaments = Tournament.query.order_by(Tournament.tournament_date.desc()).all()
    return jsonify([{
        'tournament_id': t.tournament_id,
        'tournament_date': t.tournament_date.isoformat(),
        'status': t.status,
        'total_teams': t.total_teams,
        'ace_pot_payout': float(t.ace_pot_payout) if t.ace_pot_payout else 0.00
    } for t in tournaments])

if __name__ == '__main__':
    # Test database connection
    try:
        with app.app_context():
            with db.engine.connect() as conn:
                conn.execute(db.text('SELECT 1'))
        print("Database connection successful!")
    except Exception as e:
        print(f"Database connection failed: {e}")
    
    # Run in debug mode for local development
    app.run(debug=True, host='0.0.0.0', port=5000)
