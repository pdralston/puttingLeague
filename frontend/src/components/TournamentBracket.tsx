import React, { useEffect, useState } from 'react';
import { API_BASE_URL } from '../config/api';
import Bracket from './Bracket';
import { Tournament, Match } from '../types/tournament';

interface TournamentBracketProps {
  tournamentId: number;
  onBack?: () => void;
}

const TournamentBracket: React.FC<TournamentBracketProps> = ({ tournamentId, onBack }) => {
  const [tournament, setTournament] = useState<Tournament | null>(null);
  const [tournamentStatus, setTournamentStatus] = useState<string>('');

  useEffect(() => {
    Promise.all([
      fetch(`${API_BASE_URL}/api/tournaments/${tournamentId}/matches`).then(res => res.json()),
      fetch(`${API_BASE_URL}/api/tournaments/${tournamentId}/teams`).then(res => res.json()),
      fetch(`${API_BASE_URL}/api/tournaments?id=${tournamentId}`).then(res => res.json())
    ]).then(([matches, teams, tournamentData]) => {
      setTournament({ id: tournamentId, name: `Tournament ${tournamentId}`, teams, matches });
      setTournamentStatus(tournamentData.status);
    });
  }, [tournamentId]);

  const getMatchesInProgress = (): Match[] => {
    if (!tournament) return [];
    return tournament.matches.filter(match => match.match_status === 'In_Progress');
  };

  const getTeamName = (teamId?: number | null): string => {
    if (!teamId || !tournament) return 'TBD';
    const team = tournament.teams.find(t => t.team_id === teamId);
    if (!team) return 'TBD';
    
    const player1Name = team.player1_nickname || team.player1_name || `Player ${team.player1_id}`;
    const player2Name = team.player2_id ? (team.player2_nickname || team.player2_name || `Player ${team.player2_id}`) : '';
    
    return team.is_ghost_team ? player1Name : `${player1Name} & ${player2Name}`;
  };

  const isByeMatch = (match: Match): boolean => {
    return match.team2_id === null;
  };

  const handleScoreMatch = async (matchId: number, team1Score: number, team2Score: number) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/tournaments/${tournamentId}/matches/${matchId}/score`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ team1_score: team1Score, team2_score: team2Score })
      });
      
      if (response.ok) {
        const [matches, teams] = await Promise.all([
          fetch(`${API_BASE_URL}/api/tournaments/${tournamentId}/matches`).then(res => res.json()),
          fetch(`${API_BASE_URL}/api/tournaments/${tournamentId}/teams`).then(res => res.json())
        ]);
        setTournament({ id: tournamentId, name: `Tournament ${tournamentId}`, teams, matches });
      }
    } catch (error) {
      console.error('Failed to score match:', error);
    }
  };

  const handleStartMatch = async (matchId: number) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/tournaments/${tournamentId}/matches/${matchId}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (response.ok) {
        const [matches, teams] = await Promise.all([
          fetch(`${API_BASE_URL}/api/tournaments/${tournamentId}/matches`).then(res => res.json()),
          fetch(`${API_BASE_URL}/api/tournaments/${tournamentId}/teams`).then(res => res.json())
        ]);
        setTournament({ id: tournamentId, name: `Tournament ${tournamentId}`, teams, matches });
      }
    } catch (error) {
      console.error('Failed to start match:', error);
    }
  };

  const handleStartTournament = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/tournaments/${tournamentId}/status`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'In_Progress' })
      });

      if (response.ok) {
        setTournamentStatus('In_Progress');
      }
    } catch (error) {
      console.error('Failed to start tournament:', error);
    }
  };

  if (!tournament) {
    return <div className="loading">Loading tournament...</div>;
  }

  const matchesInProgress = getMatchesInProgress();

  return (
    <div className="tournament-bracket">
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
      
      <div className="tournament-content" style={{ position: 'relative' }}>
        {tournamentStatus === 'Scheduled' && (
          <div className="tournament-overlay">
            <div className="overlay-content">
              <h2>Tournament Ready to Start</h2>
              <p>This tournament is scheduled and ready to begin.</p>
              <button className="start-tournament-button" onClick={handleStartTournament}>
                Start Tournament
              </button>
            </div>
          </div>
        )}
        
        {tournamentStatus === 'Completed' && (
          <div className="tournament-overlay">
            <div className="overlay-content">
              <h2>Tournament Complete!</h2>
              <p>This tournament has finished. Check the bracket for final results.</p>
              <button className="close-overlay-button" onClick={() => setTournamentStatus('')}>
                Close
              </button>
            </div>
          </div>
        )}
        
        <div className="brackets">
          {tournament.matches.filter(m => m.round_type === 'Winners').length > 0 && (
            <Bracket 
              matches={tournament.matches.filter(m => m.round_type === 'Winners')}
              allMatches={tournament.matches}
              teams={tournament.teams}
              players={[]}
              title="Winners Bracket"
              onScoreMatch={handleScoreMatch}
              onStartMatch={handleStartMatch}
            />
          )}
          {tournament.matches.filter(m => m.round_type === 'Losers').length > 0 && (
            <Bracket 
              matches={tournament.matches.filter(m => m.round_type === 'Losers')}
              allMatches={tournament.matches}
              teams={tournament.teams}
              players={[]}
              title="Losers Bracket"
              onScoreMatch={handleScoreMatch}
              onStartMatch={handleStartMatch}
            />
          )}
          {tournament.matches.filter(m => m.round_type === 'Championship' && (m.team1_id && m.team2_id)).length > 0 && (
            <div className="championship-section">
              <Bracket 
                matches={tournament.matches.filter(m => m.round_type === 'Championship')}
                allMatches={tournament.matches}
                teams={tournament.teams}
                players={[]}
                title="🏆 Championship"
                onScoreMatch={handleScoreMatch}
                onStartMatch={handleStartMatch}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default TournamentBracket;
