from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os
from datetime import datetime
from database import db

load_dotenv()
app = Flask(__name__)
CORS(app, supports_credentials=True)

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

app.register_blueprint(auth_bp)
app.register_blueprint(players_bp)
app.register_blueprint(tournaments_bp)
app.register_blueprint(matches_bp)
app.register_blueprint(ace_pot_bp)

@app.route('/')
def health_check():
    return jsonify({"status": "DG Putt API is running", "timestamp": datetime.now().isoformat()})

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
    app.run(debug=True, host='0.0.0.0', port=5000)
