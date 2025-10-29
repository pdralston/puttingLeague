import React from 'react';
import { Match as MatchType, Team } from '../types/tournament';

interface BracketViewProps {
  matches: MatchType[];
  teams: Team[];
  title: string;
}

const BracketView: React.FC<BracketViewProps> = ({ matches, teams, title }) => {
  const rounds = matches.reduce((acc, match) => {
    if (!acc[match.round_number]) acc[match.round_number] = [];
    acc[match.round_number].push(match);
    return acc;
  }, {} as Record<number, MatchType[]>);

  const getTeamName = (teamId?: number): string => {
    if (!teamId) return 'TBD';
    const team = teams.find(t => t.team_id === teamId);
    if (!team) return 'TBD';
    
    const player1Name = team.player1_name || `Player ${team.player1_id}`;
    const player2Name = team.player2_name || (team.player2_id ? `Player ${team.player2_id}` : '');
    
    return team.is_ghost_team ? player1Name : `${player1Name} & ${player2Name}`;
  };

  const getWinner = (match: MatchType) => {
    if (match.match_status !== 'Completed') return null;
    if (match.team1_score !== null && match.team1_score !== undefined && 
        match.team2_score !== null && match.team2_score !== undefined) {
      return match.team1_score > match.team2_score ? match.team1_id : match.team2_id;
    }
    return null;
  };

  return (
    <div className="bracket-view">
      <h3>{title}</h3>
      <div className="rounds">
        {Object.entries(rounds)
          .sort(([a], [b]) => parseInt(a) - parseInt(b))
          .map(([roundNum, roundMatches]) => (
            <div key={roundNum} className="round">
              <h4>Round {roundNum}</h4>
              {roundMatches.map(match => {
                const winner = getWinner(match);
                return (
                  <div key={match.match_id} className="match">
                    <div className="match-header">
                      <span className="match-number">Match {match.match_id}</span>
                    </div>
                    <div className="team-container">
                      <div className={`team ${winner === match.team1_id ? 'winner' : ''}`}>
                        <span className="team-name">{getTeamName(match.team1_id)}</span>
                        <span className="team-score">{match.team1_score ?? ''}</span>
                      </div>
                      <div className={`team ${winner === match.team2_id ? 'winner' : ''}`}>
                        <span className="team-name">{getTeamName(match.team2_id)}</span>
                        <span className="team-score">{match.team2_score ?? ''}</span>
                      </div>
                    </div>
                    <div className={`match-status ${match.match_status.toLowerCase().replace('_', '-')}`}>
                      {match.match_status.replace('_', ' ')}
                    </div>
                  </div>
                );
              })}
            </div>
          ))}
      </div>
    </div>
  );
};

export default BracketView;
