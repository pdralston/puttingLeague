from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
from dotenv import load_dotenv
import os
from datetime import datetime
from database import db

load_dotenv()
# Load production environment only when deployed (not in local development)
if os.getenv('AWS_EXECUTION_ENV') and os.path.exists('.env.production'):
    load_dotenv('.env.production', override=True)
app = Flask(__name__)
CORS(app, supports_credentials=True)

# Get WebSocket allowed origins from environment
websocket_origins = os.getenv('WEBSOCKET_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',')
socketio = SocketIO(app, cors_allowed_origins=websocket_origins)

def create_admin_user():
    """Create default admin user if it doesn't exist"""
    from models import User
    
    admin_username = os.getenv('ADMIN_USERNAME', 'admin')
    admin_password = os.getenv('ADMIN_PASSWORD', 'admin123')
    
    try:
        existing_user = User.query.filter_by(username=admin_username).first()
        if not existing_user:
            admin_user = User(username=admin_username, role='Admin')
            admin_user.set_password(admin_password)
            db.session.add(admin_user)
            db.session.commit()
            print(f"Created admin user: {admin_username}")
    except Exception as e:
        print(f"Error creating admin user: {e}")
        db.session.rollback()

# Session configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL') or \
    f"mysql+pymysql://{os.environ.get('DB_USER', 'root')}:" \
    f"{os.environ.get('DB_PASSWORD', 'password')}@" \
    f"{os.environ.get('DB_HOST', '127.0.0.1')}:" \
    f"{os.environ.get('DB_PORT', '3306')}/" \
    f"{os.environ.get('DB_NAME', 'dgputt')}"

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Register blueprints
from routes.players import players_bp
from routes.tournaments import tournaments_bp
from routes.matches import matches_bp
from routes.ace_pot import ace_pot_bp
from routes.auth import auth_bp
from routes.admin_audit import admin_audit_bp

app.register_blueprint(auth_bp)
app.register_blueprint(players_bp)
app.register_blueprint(tournaments_bp)
app.register_blueprint(matches_bp)
app.register_blueprint(ace_pot_bp)
app.register_blueprint(admin_audit_bp)

@app.route('/')
def health_check():
    return jsonify({"status": "DG Putt API is running", "timestamp": datetime.now().isoformat()})

# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('join_tournament')
def handle_join_tournament(data):
    tournament_id = data.get('tournament_id')
    if tournament_id:
        from flask_socketio import join_room
        join_room(f'tournament_{tournament_id}')
        print(f'Client joined tournament {tournament_id}')

@socketio.on('leave_tournament')
def handle_leave_tournament(data):
    tournament_id = data.get('tournament_id')
    if tournament_id:
        from flask_socketio import leave_room
        leave_room(f'tournament_{tournament_id}')
        print(f'Client left tournament {tournament_id}')

if __name__ == '__main__':
    # Test database connection
    try:
        with app.app_context():
            with db.engine.connect() as conn:
                conn.execute(db.text('SELECT 1'))
            print("Database connection successful!")
            create_admin_user()
    except Exception as e:
        print(f"Database connection failed: {e}")
    
    # Run in debug mode for local development
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
