import React, { useState } from 'react';
import { Match as MatchType, Team } from '../types/tournament';
import { getTeamName, getTeamDisplayName, findTeamById } from '../utils/teamUtils';

interface MatchProps {
  match: MatchType;
  allMatches: MatchType[];
  teams: Team[];
  players: any[];
  onStartMatch?: (matchId: number) => void;
  onScoreMatch?: (matchId: number, team1Score: number, team2Score: number) => void;
}

const Match: React.FC<MatchProps> = ({ match, allMatches, teams, players, onStartMatch, onScoreMatch }) => {
  const [showScorePopup, setShowScorePopup] = useState(false);
  const [team1Score, setTeam1Score] = useState('');
  const [team2Score, setTeam2Score] = useState('');

  const handleScoreSubmit = () => {
    const score1 = parseInt(team1Score);
    const score2 = parseInt(team2Score);
    if (!isNaN(score1) && !isNaN(score2) && onScoreMatch) {
      onScoreMatch(match.match_id, score1, score2);
      setShowScorePopup(false);
      setTeam1Score('');
      setTeam2Score('');
    }
  };

  const isByeMatch = () => {
    return match.team2_id === null && match.match_status === 'Scheduled';
  };


  const getWinner = () => {
    if (match.match_status !== 'Completed') {
      return null;
    }
    if (match.team1_score !== null && match.team1_score !== undefined && 
        match.team2_score !== null && match.team2_score !== undefined) {
      return match.team1_score > match.team2_score ? match.team1_id : match.team2_id;
    }
    return null;
  };

  const getTeamDisplay = (teamId?: number, isTeam1: boolean = true) => {
    if (teamId) {
      const team = findTeamById(teams, teamId);
      if (team) {
        return getTeamDisplayName(team);
      }
      return `Team ${teamId}`;
    }
    
    // Find matches that feed into this match
    const feedingMatches = allMatches.filter(m => 
      m.winner_advances_to_match_id === match.match_id || 
      m.loser_advances_to_match_id === match.match_id
    ).sort((a, b) => a.match_order - b.match_order);
    
    if (feedingMatches.length === 0) {
      return 'TBD';
    }
    
    if (feedingMatches.length === 1) {
      // Only one feeding match - determine which slot gets which team
      const feedingMatch = feedingMatches[0];
      const isWinnerAdvancing = feedingMatch.winner_advances_to_match_id === match.match_id;
      
      // For matches with one team already seeded, the empty slot gets the feeding match result
      if (match.team1_id && !match.team2_id) {
        return isTeam1 ? getTeamName(teams, match.team1_id) : `${isWinnerAdvancing ? 'Winner' : 'Loser'} ${feedingMatch.match_order}`;
      } else if (!match.team1_id && match.team2_id) {
        return isTeam1 ? `${isWinnerAdvancing ? 'Winner' : 'Loser'} ${feedingMatch.match_order}` : getTeamName(teams, match.team2_id);
      } else {
        // Neither team seeded yet
        if (isTeam1) {
          return `${isWinnerAdvancing ? 'Winner' : 'Loser'} ${feedingMatch.match_order}`;
        } else {
          if (match.round_type === 'Losers') {
            return 'Bye/Seed';
          } else {
            return 'Bye';
          }
        }
      }
    }
    
    // Multiple feeding matches - assign based on position
    const feedingMatch = isTeam1 ? feedingMatches[0] : feedingMatches[1];
    const isWinnerAdvancing = feedingMatch.winner_advances_to_match_id === match.match_id;
    return `${isWinnerAdvancing ? 'Winner' : 'Loser'} ${feedingMatch.match_order}`;
  };

  const winner = getWinner();

  // Debug logging
  if (match.match_order === 1) {
    console.log('Match 1 status:', match.match_status, 'onScoreMatch exists:', !!onScoreMatch);
  }

  return (
    <div className="match">
      <div className="match-header">
        <span className="match-number">Match {match.match_order}</span>
        {match.match_status === 'In_Progress' && match.station_assignment && (
          <span className="station-bubble">Station {match.station_assignment}</span>
        )}
        <span className="match-score">Score</span>
      </div>
      <div className={`team ${winner && winner === match.team1_id ? 'winner' : ''}`}>
        <span className="team-name">{getTeamDisplay(match.team1_id, true)}</span>
        {match.team1_score !== undefined && match.team1_score !== null && (
          <span className="team-score">{match.team1_score}</span>
        )}
      </div>
      <div className={`team ${winner && winner === match.team2_id ? 'winner' : ''}`}>
        <span className="team-name">{getTeamDisplay(match.team2_id, false)}</span>
        {match.team2_score !== undefined && match.team2_score !== null && (
          <span className="team-score">{match.team2_score}</span>
        )}
      </div>
      {match.match_status !== 'Pending' && (
        <div className={`match-status ${match.match_status.toLowerCase().replace('_', '-')}`}>
          {match.match_status}
        </div>
      )}
      {match.match_status === 'Scheduled' && onStartMatch && !isByeMatch() && (
        <button 
          className="start-button" 
          onClick={() => onStartMatch(match.match_id)}
        >
          ▶ Start
        </button>
      )}

      {match.match_status === 'In_Progress' && onScoreMatch && (
        <button 
          className="score-button" 
          onClick={() => {
            console.log('Score button clicked for match', match.match_id);
            setShowScorePopup(true);
          }}
        >
          📊 Score
        </button>
      )}

      {match.match_status === 'Completed' && onScoreMatch && (
        <div className="edit-overlay" onClick={() => {
          setTeam1Score(match.team1_score?.toString() || '');
          setTeam2Score(match.team2_score?.toString() || '');
          setShowScorePopup(true);
        }}>
          ✏️ Edit
        </div>
      )}
      
      {showScorePopup && (
        <div className="score-popup-overlay">
          <div className="score-popup" onClick={(e) => e.stopPropagation()}>
            <h4>{match.match_status === 'Completed' ? 'Edit Scores' : 'Enter Scores'}</h4>
            <div className="score-input">
              <label>{getTeamDisplay(match.team1_id, true)}</label>
              <input 
                type="number" 
                value={team1Score} 
                onChange={(e) => setTeam1Score(e.target.value)}
                min="0"
              />
            </div>
            <div className="score-input">
              <label>{getTeamDisplay(match.team2_id, false)}</label>
              <input 
                type="number" 
                value={team2Score} 
                onChange={(e) => setTeam2Score(e.target.value)}
                min="0"
              />
            </div>
            <div className="score-buttons">
              <button onClick={() => setShowScorePopup(false)}>Cancel</button>
              <button onClick={handleScoreSubmit}>
                {match.match_status === 'Completed' ? 'Update' : 'Submit'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Match;
