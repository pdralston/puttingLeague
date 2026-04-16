from flask import Blueprint, jsonify, request
from datetime import date
from decimal import Decimal
from database import db
from models import Season, RegisteredPlayer, Tournament, TournamentRegistration, Team, AcePot
from routes.auth import require_auth

archive_bp = Blueprint('archive', __name__)


@archive_bp.route('/api/archive/preview', methods=['GET'])
@require_auth(['Admin'])
def archive_preview():
    """Return quick stats for the current season to display in the modal."""
    current_tournaments = Tournament.query.filter_by(season_id=None).filter(
        Tournament.status != 'Pending'
    ).all()

    if not current_tournaments:
        return jsonify({
            'start_date': None,
            'end_date': None,
            'event_count': 0,
            'unique_participants': 0,
            'total_participants': 0
        })

    tournament_ids = [t.tournament_id for t in current_tournaments]
    dates = [t.tournament_date for t in current_tournaments]

    registrations = TournamentRegistration.query.filter(
        TournamentRegistration.tournament_id.in_(tournament_ids)
    ).all()

    unique_participants = len({r.player_id for r in registrations})
    total_participants = len(registrations)

    return jsonify({
        'start_date': min(dates).isoformat(),
        'end_date': max(dates).isoformat(),
        'event_count': len(current_tournaments),
        'unique_participants': unique_participants,
        'total_participants': total_participants
    })


@archive_bp.route('/api/archive', methods=['POST'])
@require_auth(['Admin'])
def perform_archive():
    """
    Archive the current season:
    1. Create a Season record
    2. Tag current tournaments with the new season_id
    3. Update player lifetime stats, reset seasonal stats, prune inactive players
    4. Promote Am division winners to Pro
    5. Collapse ace pot to a single carry-over entry
    """
    import re
    data = request.get_json()
    season_name = (data or {}).get('season_name', '').strip()
    if not season_name:
        return jsonify({'error': 'season_name is required'}), 400
    if len(season_name) > 100:
        return jsonify({'error': 'season_name must be 100 characters or fewer'}), 400
    if not re.match(r'^[\w\s\-\.]+$', season_name):
        return jsonify({'error': 'season_name contains invalid characters'}), 400

    try:
        # --- Determine season date range from current (unarchived, non-Pending) tournaments ---
        current_tournaments = Tournament.query.filter_by(season_id=None).filter(
            Tournament.status != 'Pending'
        ).all()

        tournament_ids = [t.tournament_id for t in current_tournaments]
        dates = [t.tournament_date for t in current_tournaments]
        start_date = min(dates) if dates else date.today()
        end_date = max(dates) if dates else date.today()

        # --- Create season record ---
        season = Season(season_name=season_name, start_date=start_date, end_date=end_date)
        db.session.add(season)
        db.session.flush()  # get season_id

        # --- Tag tournaments ---
        for t in current_tournaments:
            t.season_id = season.season_id

        # --- Update player stats ---
        players = RegisteredPlayer.query.all()
        for player in players:
            # Determine participation in current season
            player_regs = TournamentRegistration.query.filter(
                TournamentRegistration.player_id == player.player_id,
                TournamentRegistration.tournament_id.in_(tournament_ids)
            ).all() if tournament_ids else []

            # Prune players with no history at all
            if not player_regs:
                any_team = Team.query.filter(
                    db.or_(Team.player1_id == player.player_id, Team.player2_id == player.player_id)
                ).first()
                if not any_team:
                    db.session.delete(player)
                    continue

            # Accumulate lifetime earnings from seasonal cash
            player.lifetime_earnings = (player.lifetime_earnings or Decimal('0')) + (player.seasonal_cash or Decimal('0'))

            # Count ace pot wins this season
            ace_pot_wins = sum(1 for r in player_regs if r.bought_ace_pot)
            player.lifetime_ace_pots = (player.lifetime_ace_pots or 0) + ace_pot_wins

            # Events participated
            player.events_participated = (player.events_participated or 0) + len(player_regs)

            # Seasonal wins (first place finishes this season)
            wins_this_season = Team.query.filter(
                db.or_(Team.player1_id == player.player_id, Team.player2_id == player.player_id),
                Team.tournament_id.in_(tournament_ids),
                Team.final_place == 1
            ).count() if tournament_ids else 0
            player.seasonal_wins = (player.seasonal_wins or 0) + wins_this_season

            # Recalculate average place across all seasons
            all_teams = Team.query.filter(
                db.or_(Team.player1_id == player.player_id, Team.player2_id == player.player_id),
                Team.final_place.isnot(None)
            ).all()
            if all_teams:
                player.average_place = Decimal(str(sum(t.final_place for t in all_teams) / len(all_teams)))

            # Promote Am winner to Pro
            if player.division == 'Am' and wins_this_season > 0:
                player.division = 'Pro'

            # Reset seasonal stats
            player.seasonal_points = 0
            player.seasonal_cash = Decimal('0.00')

        # --- Collapse ace pot ---
        all_entries = AcePot.query.all()
        balance = sum(e.amount for e in all_entries)
        for entry in all_entries:
            db.session.delete(entry)
        db.session.flush()

        if balance != 0:
            carry_over = AcePot(
                tournament_id=None,
                date=date.today(),
                description='Season Carry Over',
                amount=balance
            )
            db.session.add(carry_over)

        db.session.commit()
        return jsonify({'success': True, 'season_id': season.season_id, 'season_name': season.season_name})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
