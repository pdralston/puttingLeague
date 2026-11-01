from flask import Blueprint, jsonify, request
from datetime import date
from decimal import Decimal
from database import db
from models import (
    Season, RegisteredPlayer, Tournament, TournamentRegistration,
    Team, Match, AcePot, TeamHistory,
)
from routes.auth import require_auth
from routes.matches import _is_team_undefeated

archive_bp = Blueprint('archive', __name__)


def _get_am_point_leaders():
    """
    Return (max_points, [RegisteredPlayer, ...]) for the Am division based on
    current-season seasonal_points.

    The season winner is the Am player with the most seasonal points at archive
    time. Players with zero (or negative) points are never considered winners.
    If multiple players share the top non-zero total it is a tie and the list
    has more than one entry.
    """
    am_players = RegisteredPlayer.query.filter_by(division='Am').all()
    if not am_players:
        return 0, []

    max_points = max((p.seasonal_points or 0) for p in am_players)
    if max_points <= 0:
        return max_points, []

    leaders = [p for p in am_players if (p.seasonal_points or 0) == max_points]
    return max_points, leaders


def _delete_tournament_cascade(tournament_id):
    """
    Delete a tournament and its dependent rows in FK-safe order.

    Mirrors the deletion order used by tournaments.delete_tournament. Does NOT
    reverse seasonal points/cash: incomplete tournaments never awarded points
    (points are only awarded on completion), so there is nothing to reverse.
    Teammate-history cleanup is applied for any teams that were already formed.
    """
    teams = Team.query.filter_by(tournament_id=tournament_id).all()
    for team in teams:
        if not team.is_ghost_team and team.player2_id:
            for player_id, teammate_id in [
                (team.player1_id, team.player2_id),
                (team.player2_id, team.player1_id),
            ]:
                history = TeamHistory.query.filter_by(
                    player_id=player_id, teammate_id=teammate_id
                ).first()
                if history:
                    history.times_paired -= 1
                    if history.times_paired <= 0:
                        db.session.delete(history)

    Match.query.filter_by(tournament_id=tournament_id).delete()
    Team.query.filter_by(tournament_id=tournament_id).delete()
    TournamentRegistration.query.filter_by(tournament_id=tournament_id).delete()
    AcePot.query.filter_by(tournament_id=tournament_id).delete()
    Tournament.query.filter_by(tournament_id=tournament_id).delete()


@archive_bp.route('/api/archive/preview', methods=['GET'])
@require_auth(['Admin'])
def archive_preview():
    """
    Return quick stats for the current season to display in the modal.

    Only Completed tournaments are archived. Any current-season tournament that
    is not Completed will be DELETED at archive time; those are surfaced here so
    the admin can see what will be removed. Also reports the Am-division point
    leader(s) and whether promotion is a tie that requires admin resolution.
    """
    current = Tournament.query.filter_by(season_id=None).all()
    completed = [t for t in current if t.status == 'Completed']
    incomplete = [t for t in current if t.status != 'Completed']

    max_points, leaders = _get_am_point_leaders()

    if not completed:
        return jsonify({
            'start_date': None,
            'end_date': None,
            'event_count': 0,
            'unique_participants': 0,
            'total_participants': 0,
            'incomplete_to_delete': [
                {'tournament_id': t.tournament_id,
                 'tournament_date': t.tournament_date.isoformat(),
                 'status': t.status}
                for t in incomplete
            ],
            'am_leaders': [
                {'player_id': p.player_id, 'player_name': p.player_name,
                 'seasonal_points': p.seasonal_points or 0}
                for p in leaders
            ],
            'am_promotion_tie': len(leaders) > 1,
            'can_archive': False,
        })

    completed_ids = [t.tournament_id for t in completed]
    dates = [t.tournament_date for t in completed]

    registrations = TournamentRegistration.query.filter(
        TournamentRegistration.tournament_id.in_(completed_ids)
    ).all()

    unique_participants = len({r.player_id for r in registrations})
    total_participants = len(registrations)

    return jsonify({
        'start_date': min(dates).isoformat(),
        'end_date': max(dates).isoformat(),
        'event_count': len(completed),
        'unique_participants': unique_participants,
        'total_participants': total_participants,
        'incomplete_to_delete': [
            {'tournament_id': t.tournament_id,
             'tournament_date': t.tournament_date.isoformat(),
             'status': t.status}
            for t in incomplete
        ],
        'am_leaders': [
            {'player_id': p.player_id, 'player_name': p.player_name,
             'seasonal_points': p.seasonal_points or 0}
            for p in leaders
        ],
        'am_promotion_tie': len(leaders) > 1,
        'can_archive': True,
    })


@archive_bp.route('/api/archive', methods=['POST'])
@require_auth(['Admin'])
def perform_archive():
    """
    Archive the current season:
    1. Validate there is at least one Completed tournament to archive.
    2. Resolve Am-division season-winner promotion (prompt admin on a tie).
    3. Create a Season record.
    4. Tag Completed tournaments with the new season_id.
    5. Delete all incomplete (non-Completed) tournaments.
    6. Update player lifetime stats, reset seasonal stats, prune inactive players.
    7. Promote the Am season point leader(s) selected for promotion to Pro.
    8. Collapse the ace pot to a single carry-over entry.

    Tie handling for Am promotion:
      - If exactly one Am player leads on seasonal_points, they are promoted.
      - If multiple Am players tie for the lead, the request must include
        `tie_resolution`: a list of player_ids (a subset of the tied leaders)
        to promote. May be an empty list to promote no one. If the tie exists
        and `tie_resolution` is absent, respond 409 with the tied candidates so
        the admin can choose.
    """
    import re
    data = request.get_json() or {}
    season_name = data.get('season_name', '').strip()
    if not season_name:
        return jsonify({'error': 'season_name is required'}), 400
    if len(season_name) > 100:
        return jsonify({'error': 'season_name must be 100 characters or fewer'}), 400
    if not re.match(r'^[\w\s\-\.]+$', season_name):
        return jsonify({'error': 'season_name contains invalid characters'}), 400

    try:
        current = Tournament.query.filter_by(season_id=None).all()
        completed = [t for t in current if t.status == 'Completed']
        incomplete = [t for t in current if t.status != 'Completed']

        # --- Empty-season guard ---
        if not completed:
            return jsonify({'error': 'No completed tournaments to archive'}), 400

        # --- Resolve Am season-winner promotion (before any seasonal reset) ---
        _, leaders = _get_am_point_leaders()
        leader_ids = {p.player_id for p in leaders}
        promote_ids = set()

        if len(leaders) == 1:
            promote_ids = leader_ids
        elif len(leaders) > 1:
            tie_resolution = data.get('tie_resolution')
            if tie_resolution is None:
                # Prompt the admin to choose among the tied leaders.
                return jsonify({
                    'error': 'am_promotion_tie',
                    'message': 'Multiple Am players are tied for the season '
                               'points lead. Select which, if any, to promote.',
                    'tied_leaders': [
                        {'player_id': p.player_id,
                         'player_name': p.player_name,
                         'seasonal_points': p.seasonal_points or 0}
                        for p in leaders
                    ],
                }), 409
            if not isinstance(tie_resolution, list):
                return jsonify({'error': 'tie_resolution must be a list of player_ids'}), 400
            try:
                selected = {int(pid) for pid in tie_resolution}
            except (TypeError, ValueError):
                return jsonify({'error': 'tie_resolution must contain integer player_ids'}), 400
            invalid = selected - leader_ids
            if invalid:
                return jsonify({
                    'error': 'tie_resolution contains player_ids that are not '
                             'tied Am leaders',
                    'invalid_player_ids': sorted(invalid),
                }), 400
            promote_ids = selected
        # len(leaders) == 0 -> no eligible winner, promote_ids stays empty

        completed_ids = [t.tournament_id for t in completed]
        dates = [t.tournament_date for t in completed]
        start_date = min(dates)
        end_date = max(dates)

        # --- Create season record ---
        season = Season(season_name=season_name, start_date=start_date, end_date=end_date)
        db.session.add(season)
        db.session.flush()  # get season_id

        # --- Tag Completed tournaments ---
        for t in completed:
            t.season_id = season.season_id

        # --- Delete incomplete tournaments (FK-safe) ---
        for t in incomplete:
            _delete_tournament_cascade(t.tournament_id)
        db.session.flush()

        # --- Update player stats ---
        players = RegisteredPlayer.query.all()
        for player in players:
            # Participation in the archived (Completed) tournaments
            player_regs = TournamentRegistration.query.filter(
                TournamentRegistration.player_id == player.player_id,
                TournamentRegistration.tournament_id.in_(completed_ids)
            ).all()

            # Prune players with no history at all
            if not player_regs:
                any_team = Team.query.filter(
                    db.or_(Team.player1_id == player.player_id,
                           Team.player2_id == player.player_id)
                ).first()
                if not any_team:
                    db.session.delete(player)
                    continue

            # Accumulate lifetime earnings from seasonal cash
            player.lifetime_earnings = (player.lifetime_earnings or Decimal('0')) + \
                (player.seasonal_cash or Decimal('0'))

            # Count ace pot WINS this season: the player was on a team that
            # finished 1st AND went undefeated. (Previously this incorrectly
            # counted ace-pot buy-ins via bought_ace_pot.)
            ace_pot_wins = 0
            winning_teams = Team.query.filter(
                db.or_(Team.player1_id == player.player_id,
                       Team.player2_id == player.player_id),
                Team.tournament_id.in_(completed_ids),
                Team.final_place == 1
            ).all()
            for wt in winning_teams:
                if _is_team_undefeated(wt.tournament_id, wt.team_id):
                    ace_pot_wins += 1
            player.lifetime_ace_pots = (player.lifetime_ace_pots or 0) + ace_pot_wins

            # Events participated
            player.events_participated = (player.events_participated or 0) + len(player_regs)

            # Seasonal wins (first place finishes in archived tournaments)
            wins_this_season = Team.query.filter(
                db.or_(Team.player1_id == player.player_id,
                       Team.player2_id == player.player_id),
                Team.tournament_id.in_(completed_ids),
                Team.final_place == 1
            ).count()
            player.seasonal_wins = (player.seasonal_wins or 0) + wins_this_season

            # Recalculate average place across all seasons
            all_teams = Team.query.filter(
                db.or_(Team.player1_id == player.player_id,
                       Team.player2_id == player.player_id),
                Team.final_place.isnot(None)
            ).all()
            if all_teams:
                player.average_place = Decimal(
                    str(sum(t.final_place for t in all_teams) / len(all_teams))
                )

            # Promote Am season point leader(s) selected for promotion
            if player.division == 'Am' and player.player_id in promote_ids:
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
        return jsonify({
            'success': True,
            'season_id': season.season_id,
            'season_name': season.season_name,
            'archived_tournaments': len(completed),
            'deleted_incomplete_tournaments': len(incomplete),
            'promoted_player_ids': sorted(promote_ids),
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
