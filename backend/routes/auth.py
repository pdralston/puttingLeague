from flask import Blueprint, request, jsonify, session
from database import db
from models import User
from functools import wraps

auth_bp = Blueprint('auth', __name__)

def require_auth(allowed_roles=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({'error': 'Authentication required'}), 401
            
            user = User.query.get(session['user_id'])
            if not user:
                return jsonify({'error': 'Invalid session'}), 401
            
            if allowed_roles and user.role not in allowed_roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Username and password required'}), 400
    
    user = User.query.filter_by(username=data['username']).first()
    if not user or not user.check_password(data['password']):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    session['user_id'] = user.user_id
    session['role'] = user.role
    
    return jsonify({
        'user_id': user.user_id,
        'username': user.username,
        'role': user.role
    })

@auth_bp.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'})

@auth_bp.route('/api/auth/me', methods=['GET'])
def get_current_user():
    if 'user_id' not in session:
        return jsonify({'role': 'Viewer'})
    
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return jsonify({'role': 'Viewer'})
    
    return jsonify({
        'user_id': user.user_id,
        'username': user.username,
        'role': user.role
    })

@auth_bp.route('/api/auth/users', methods=['POST'])
@require_auth(['Admin'])
def create_user():
    data = request.get_json()
    if not data or not all(k in data for k in ['username', 'password', 'role']):
        return jsonify({'error': 'Username, password, and role required'}), 400
    
    if data['role'] not in ['Admin', 'Director']:
        return jsonify({'error': 'Invalid role'}), 400
    
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 400
    
    user = User(username=data['username'], role=data['role'])
    user.set_password(data['password'])
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'user_id': user.user_id,
        'username': user.username,
        'role': user.role
    }), 201

@auth_bp.route('/api/auth/users', methods=['GET'])
@require_auth(['Admin'])
def get_users():
    users = User.query.all()
    return jsonify([{
        'user_id': u.user_id,
        'username': u.username,
        'role': u.role,
        'created_at': u.created_at.isoformat()
    } for u in users])

@auth_bp.route('/api/auth/users/<int:user_id>', methods=['PUT'])
@require_auth(['Admin', 'Director'])
def update_user(user_id):
    from flask import session
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Directors can only edit themselves
    if session.get('role') == 'Director' and session.get('user_id') != user_id:
        return jsonify({'error': 'Directors can only edit their own profile'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    if 'username' in data:
        # Check if username already exists
        existing = User.query.filter(User.username == data['username'], User.user_id != user_id).first()
        if existing:
            return jsonify({'error': 'Username already exists'}), 400
        user.username = data['username']
    
    if 'password' in data and data['password']:
        user.set_password(data['password'])
    
    # Only admins can change roles
    if 'role' in data and session.get('role') == 'Admin':
        if data['role'] in ['Admin', 'Director']:
            user.role = data['role']
    
    db.session.commit()
    return jsonify({
        'user_id': user.user_id,
        'username': user.username,
        'role': user.role
    })

@auth_bp.route('/api/auth/reset-data', methods=['DELETE'])
@require_auth(['Admin'])
def reset_all_data():
    try:
        # Delete in order to respect foreign key constraints
        db.session.execute(db.text('DELETE FROM matches'))
        db.session.execute(db.text('DELETE FROM teams'))
        db.session.execute(db.text('DELETE FROM tournament_registrations'))
        db.session.execute(db.text('DELETE FROM ace_pot'))
        db.session.execute(db.text('DELETE FROM tournaments'))
        db.session.execute(db.text('DELETE FROM team_history'))
        db.session.execute(db.text('DELETE FROM season_standings'))
        db.session.execute(db.text('DELETE FROM registered_players'))
        
        db.session.commit()
        return jsonify({'message': 'All data reset successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/api/auth/users/<int:user_id>', methods=['DELETE'])
@require_auth(['Admin'])
def delete_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Prevent deleting the last admin
    if user.role == 'Admin' and User.query.filter_by(role='Admin').count() <= 1:
        return jsonify({'error': 'Cannot delete the last admin'}), 400
    
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({'message': 'User deleted successfully'})
