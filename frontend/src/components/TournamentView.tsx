import React, { useEffect, useState } from 'react';
import BracketView from './BracketView';
import { Tournament, Match } from '../types/tournament';

interface TournamentViewProps {
  tournamentId: number;
  onBack?: () => void;
}

const TournamentView: React.FC<TournamentViewProps> = ({ tournamentId, onBack }) => {
  const [tournament, setTournament] = useState<Tournament | null>(null);
  const [tournamentStatus, setTournamentStatus] = useState<string>('');
  const [acePotBalance, setAcePotBalance] = useState<number>(0);

  useEffect(() => {
    Promise.all([
      fetch(`http://localhost:5000/api/tournaments/${tournamentId}/matches`).then(res => res.json()),
      fetch(`http://localhost:5000/api/tournaments/${tournamentId}/teams`).then(res => res.json()),
      fetch(`http://localhost:5000/api/tournaments?id=${tournamentId}`).then(res => res.json()),
      fetch(`http://localhost:5000/api/ace-pot`).then(res => res.json())
    ]).then(([matches, teams, tournamentData, acePotData]) => {
      setTournament({ id: tournamentId, name: `Tournament ${tournamentId}`, teams, matches });
      setTournamentStatus(tournamentData.status);
      
      // Calculate total ace pot balance
      const totalBalance = acePotData.reduce((sum: number, entry: any) => sum + entry.amount, 0);
      setAcePotBalance(totalBalance);
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

  const getTop4Teams = () => {
    if (!tournament) return [];
    return tournament.teams
      .filter(t => t.final_place && t.final_place <= 4)
      .sort((a, b) => (a.final_place || 999) - (b.final_place || 999));
  };

  const calculatePayout = (place: number, totalParticipants: number, isUndefeated: boolean = false) => {
    const totalPot = 5 * totalParticipants;
    const secondPlace = Math.min(40, totalPot - 40);
    const firstPlace = totalPot - secondPlace;
    
    if (place === 1) {
      return firstPlace + (isUndefeated ? acePotBalance : 0);
    }
    if (place === 2) return secondPlace;
    return 0;
  };

  const isTeamUndefeated = (teamId: number): boolean => {
    if (!tournament) return false;
    
    const teamMatches = tournament.matches.filter(m => 
      (m.team1_id === teamId || m.team2_id === teamId) && m.match_status === 'Completed'
    );
    
    return teamMatches.every(match => {
      if (match.team1_score === undefined || match.team2_score === undefined) return false;
      
      if (match.team1_id === teamId) {
        return match.team1_score > match.team2_score;
      } else {
        return match.team2_score > match.team1_score;
      }
    });
  };

  const getAward = (place: number, payout: number) => {
    if (place === 1 || place === 2) {
      return `$${payout}`;
    } else if (place === 3) {
      return '2 Crowlers from Hapas Brewing';
    } else if (place === 4) {
      return 'Free entry next week';
    }
    return '';
  };

  if (!tournament) {
    return <div className="loading">Loading tournament...</div>;
  }

  const matchesInProgress = getMatchesInProgress();
  const winnersMatches = tournament.matches.filter(m => m.round_type === 'Winners');
  const losersMatches = tournament.matches.filter(m => m.round_type === 'Losers');
  const championshipMatches = tournament.matches.filter(m => m.round_type === 'Championship');

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
      
      <div className="tournament-content" style={{ position: 'relative' }}>
        {tournamentStatus === 'Completed' && (
          <div className="tournament-overlay">
            <div className="overlay-content">
              <h2>Tournament Complete!</h2>
              <h3>Top 4 Finishers</h3>
              <div className="top-4-results">
                {getTop4Teams().map(team => {
                  const isUndefeated = isTeamUndefeated(team.team_id);
                  const payout = calculatePayout(team.final_place || 0, tournament.teams.length * 2, isUndefeated);
                  return (
                    <div key={team.team_id} className={`place-result ${isUndefeated && team.final_place === 1 ? 'undefeated-winner' : ''}`}>
                      <div className="place-number">{team.final_place}</div>
                      <div className="team-name">{getTeamName(team.team_id)}</div>
                      {isUndefeated && team.final_place === 1 && <div className="ace-stamp">ACE</div>}
                      <div className="award">{getAward(team.final_place || 0, payout)}</div>
                    </div>
                  );
                })}
              </div>
              <button className="close-overlay-button" onClick={() => setTournamentStatus('')}>
                Close
              </button>
            </div>
          </div>
        )}
        
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
          {championshipMatches.length > 0 && (
            <BracketView 
              matches={championshipMatches}
              teams={tournament.teams}
              title="Championship"
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default TournamentView;
