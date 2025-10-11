from flask import Flask, jsonify
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
    f"{os.environ.get('DB_HOST', '127.0.0.1')}:" \
    f"{os.environ.get('DB_PORT', '3306')}/" \
    f"{os.environ.get('DB_NAME', 'dgputt')}"

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Register blueprints
from routes.players import players_bp
from routes.tournaments import tournaments_bp

app.register_blueprint(players_bp)
app.register_blueprint(tournaments_bp)

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
    except Exception as e:
        print(f"Database connection failed: {e}")
    
    # Run in debug mode for local development
    app.run(debug=True, host='0.0.0.0', port=5000)
