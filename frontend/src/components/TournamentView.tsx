import React, { useEffect, useState } from 'react';
import BracketView from './BracketView';
import { Tournament, Match } from '../types/tournament';

interface TournamentViewProps {
  tournamentId: number;
  onBack?: () => void;
}

const TournamentView: React.FC<TournamentViewProps> = ({ tournamentId, onBack }) => {
  const [tournament, setTournament] = useState<Tournament | null>(null);

  useEffect(() => {
    Promise.all([
      fetch(`http://localhost:5000/api/tournaments/${tournamentId}/matches`).then(res => res.json()),
      fetch(`http://localhost:5000/api/tournaments/${tournamentId}/teams`).then(res => res.json())
    ]).then(([matches, teams]) => {
      setTournament({ id: tournamentId, name: `Tournament ${tournamentId}`, teams, matches });
    });
  }, [tournamentId]);

  const getMatchesInProgress = (): Match[] => {
    if (!tournament) return [];
    return tournament.matches.filter(match => match.match_status === 'In_Progress');
  };

  const getTeamName = (teamId?: number): string => {
    if (!teamId || !tournament) return 'TBD';
    const team = tournament.teams.find(t => t.team_id === teamId);
    if (!team) return 'TBD';
    
    const player1Name = team.player1_name || `Player ${team.player1_id}`;
    const player2Name = team.player2_name || (team.player2_id ? `Player ${team.player2_id}` : '');
    
    return team.is_ghost_team ? player1Name : `${player1Name} & ${player2Name}`;
  };

  if (!tournament) {
    return <div className="loading">Loading tournament...</div>;
  }

  const matchesInProgress = getMatchesInProgress();
  const winnersMatches = tournament.matches.filter(m => m.round_type === 'Winners');
  const losersMatches = tournament.matches.filter(m => m.round_type === 'Losers');

  return (
    <div className="tournament-view">
      {matchesInProgress.length > 0 && (
        <div className="matches-in-progress">
          <h3>Matches in Progress</h3>
          <div className="active-matches">
            {matchesInProgress.map(match => (
              <div key={match.match_id} className="active-match">
                <div className="station">Station {match.station_assignment}</div>
                <div className="teams">
                  {getTeamName(match.team1_id)} vs {getTeamName(match.team2_id)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {onBack && (
        <div className="back-button-container">
          <button className="back-button" onClick={onBack}>
            ← Back to Tournaments
          </button>
        </div>
      )}
      
      <div className="tournament-content">
        <div className="brackets">
          {winnersMatches.length > 0 && (
            <BracketView 
              matches={winnersMatches}
              teams={tournament.teams}
              title="Winners Bracket"
            />
          )}
          {losersMatches.length > 0 && (
            <BracketView 
              matches={losersMatches}
              teams={tournament.teams}
              title="Losers Bracket"
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default TournamentView;
