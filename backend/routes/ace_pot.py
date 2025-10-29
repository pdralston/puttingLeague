from flask import Blueprint, jsonify
from database import db
from models import AcePot

ace_pot_bp = Blueprint('ace_pot', __name__)

@ace_pot_bp.route('/api/ace-pot', methods=['GET'])
def get_ace_pot_entries():
    entries = AcePot.query.order_by(AcePot.date.asc(), AcePot.ace_pot_id.asc()).all()
    return jsonify([{
        'ace_pot_id': entry.ace_pot_id,
        'tournament_id': entry.tournament_id,
        'date': entry.date.isoformat(),
        'description': entry.description,
        'amount': float(entry.amount)
    } for entry in entries])
