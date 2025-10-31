import React, { useState } from 'react';
import { Match as MatchType, Team } from '../types/tournament';

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
    return match.round_number !== 0 && (match.parent_match_id_one == null || match.parent_match_id_two == null) && match.team1_id !== null && match.match_status != "Completed"
  };

  const handleAdvanceBye = () => {
    if (!onScoreMatch || !isByeMatch()) return;
    
    // Case 1: Team already seeded, just advance them
    if (match.team1_id && !match.team2_id) {
      onScoreMatch(match.match_id, 1, 0);
    } else if (!match.team1_id && match.team2_id) {
      onScoreMatch(match.match_id, 0, 1);
    } 
    // Case 2: No teams seeded, find the winner from completed feeding match
    else if (!match.team1_id && !match.team2_id) {
      const feedingMatches = allMatches.filter(m => 
        m.winner_advances_to_match_id === match.match_id || 
        m.loser_advances_to_match_id === match.match_id
      );
      
      const completedFeeding = feedingMatches.find(m => m.match_status === 'Completed');
      if (completedFeeding && completedFeeding.team1_score !== undefined && completedFeeding.team2_score !== undefined) {
        // Determine which team advances and score accordingly
        let advancingTeam;
        if (completedFeeding.winner_advances_to_match_id === match.match_id) {
          advancingTeam = completedFeeding.team1_score > completedFeeding.team2_score 
            ? completedFeeding.team1_id 
            : completedFeeding.team2_id;
        } else {
          advancingTeam = completedFeeding.team1_score < completedFeeding.team2_score 
            ? completedFeeding.team1_id 
            : completedFeeding.team2_id;
        }
        
        // Score the match with the advancing team as winner
        onScoreMatch(match.match_id, 1, 0);
      }
    }
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
      const team = teams.find(t => t.team_id === teamId);
      if (team && team.player1_name) {
        return team.player2_name ? `${team.player1_name} & ${team.player2_name}` : team.player1_name;
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
      // Only one feeding match - this means one slot gets the result, other gets a bye/seed
      const feedingMatch = feedingMatches[0];
      const isWinnerAdvancing = feedingMatch.winner_advances_to_match_id === match.match_id;
      
      if (isTeam1) {
        return `${isWinnerAdvancing ? 'Winner' : 'Loser'} ${feedingMatch.match_order}`;
      } else {
        // Second slot gets a bye or direct seed - check if it's losers bracket
        if (match.round_type === 'Losers') {
          return 'Bye/Seed';
        } else {
          return 'Bye';
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
      {isByeMatch() && onScoreMatch && (
        <button 
          className="advance-button" 
          onClick={handleAdvanceBye}
        >
          ⏭ Advance
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
      
      {showScorePopup && (
        <div className="score-popup-overlay" onClick={() => setShowScorePopup(false)}>
          <div className="score-popup" onClick={(e) => e.stopPropagation()}>
            <h4>Enter Scores</h4>
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
              <button onClick={handleScoreSubmit}>Submit</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Match;
