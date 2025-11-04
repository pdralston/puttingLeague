import React, { useEffect, useState } from 'react';
import { API_BASE_URL } from '../config/api';
import Bracket from './Bracket';
import { Tournament, Match } from '../types/tournament';
import { getTeamName } from '../utils/teamUtils';

interface UnifiedTournamentViewProps {
  tournamentId: number;
  onBack?: () => void;
  showManagementActions?: boolean;
  currentUser?: { role: string };
}

const UnifiedTournamentView: React.FC<UnifiedTournamentViewProps> = ({ 
  tournamentId, 
  onBack, 
  showManagementActions = false,
  currentUser
}) => {
  const [tournament, setTournament] = useState<Tournament | null>(null);
  const [tournamentData, setTournamentData] = useState<any>(null);
  const [tournamentStatus, setTournamentStatus] = useState<string>('');
  const [newMatchData, setNewMatchData] = useState({
    stage_type: 'Group_A',
    round_type: 'Winners',
    round_number: 0,
    position_in_round: 0
  });
  const [showCompletionOverlay, setShowCompletionOverlay] = useState(false);
  const [acePotBalance, setAcePotBalance] = useState<number>(0);

  useEffect(() => {
    Promise.all([
      fetch(`${API_BASE_URL}/api/tournaments/${tournamentId}/matches`, { credentials: 'include' }).then(res => res.json()),
      fetch(`${API_BASE_URL}/api/tournaments/${tournamentId}/teams`, { credentials: 'include' }).then(res => res.json()),
      fetch(`${API_BASE_URL}/api/tournaments?id=${tournamentId}`, { credentials: 'include' }).then(res => res.json()),
      fetch(`${API_BASE_URL}/api/ace-pot`, { credentials: 'include' }).then(res => res.json())
    ]).then(([matches, teams, tournamentData, acePotData]) => {
      setTournament({ id: tournamentId, name: `Tournament ${tournamentId}`, teams, matches });
      setTournamentData(tournamentData);
      setTournamentStatus(tournamentData.status);
      setShowCompletionOverlay(tournamentData.status === 'Completed');
      
      const totalBalance = acePotData.reduce((sum: number, entry: any) => sum + entry.amount, 0);
      setAcePotBalance(totalBalance);
    });
  }, [tournamentId]);

  const getMatchesInProgress = (): Match[] => {
    if (!tournament) return [];
    return tournament.matches.filter(match => match.match_status === 'In_Progress');
  };

  const getTeamDisplayName = (teamId?: number | null): string => {
    if (!tournament) return 'TBD';
    return getTeamName(tournament.teams, teamId);
  };

  const handleScoreMatch = async (matchId: number, team1Score: number, team2Score: number) => {
    if (!showManagementActions) return;
    
    // Check if this is the last match that would complete the tournament
    const match = tournament?.matches.find(m => m.match_id === matchId);
    const isLastMatch = match?.round_type === 'Championship' && (
      match.round_number === 1 || // Second championship match
      (match.round_number === 0 && team1Score > team2Score) // First championship match with WB winner winning
    );
    
    if (isLastMatch) {
      const confirmed = window.confirm(
        'This will complete and finalize the tournament. Are you sure you want to proceed?'
      );
      if (!confirmed) return;
    }
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/tournaments/${tournamentId}/matches/${matchId}/score`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ team1_score: team1Score, team2_score: team2Score })
      });
      
      if (response.ok) {
        const [matches, teams, tournamentData] = await Promise.all([
          fetch(`${API_BASE_URL}/api/tournaments/${tournamentId}/matches`, { credentials: 'include' }).then(res => res.json()),
          fetch(`${API_BASE_URL}/api/tournaments/${tournamentId}/teams`, { credentials: 'include' }).then(res => res.json()),
          fetch(`${API_BASE_URL}/api/tournaments?id=${tournamentId}`, { credentials: 'include' }).then(res => res.json())
        ]);
        setTournament({ id: tournamentId, name: `Tournament ${tournamentId}`, teams, matches });
        setTournamentData(tournamentData);
        setTournamentStatus(tournamentData.status);
        setShowCompletionOverlay(tournamentData.status === 'Completed');
      } else {
        const error = await response.json();
        alert(`Error scoring match: ${error.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Failed to score match:', error);
      alert('Network error: Failed to score match. Please try again.');
    }
  };

  const handleCreateMatch = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/tournaments/${tournamentId}/matches`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(newMatchData)
      });
      
      if (response.ok) {
        // Refresh tournament data
        const [matches, teams, tournamentData] = await Promise.all([
          fetch(`${API_BASE_URL}/api/tournaments/${tournamentId}/matches`, { credentials: 'include' }).then(res => res.json()),
          fetch(`${API_BASE_URL}/api/tournaments/${tournamentId}/teams`, { credentials: 'include' }).then(res => res.json()),
          fetch(`${API_BASE_URL}/api/tournaments?id=${tournamentId}`, { credentials: 'include' }).then(res => res.json())
        ]);
        setTournament({ id: tournamentId, name: `Tournament ${tournamentId}`, teams, matches });
        setTournamentData(tournamentData);
        setNewMatchData({ stage_type: 'Group_A', round_type: 'Winners', round_number: 0, position_in_round: 0 });
      } else {
        const error = await response.json();
        alert(error.error);
      }
    } catch (error) {
      console.error('Failed to create match:', error);
    }
  };

  const handleStartMatch = async (matchId: number) => {
    if (!showManagementActions) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/tournaments/${tournamentId}/matches/${matchId}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include'
      });
      
      if (response.ok) {
        const [matches, teams] = await Promise.all([
          fetch(`${API_BASE_URL}/api/tournaments/${tournamentId}/matches`, { credentials: 'include' }).then(res => res.json()),
          fetch(`${API_BASE_URL}/api/tournaments/${tournamentId}/teams`, { credentials: 'include' }).then(res => res.json())
        ]);
        setTournament({ id: tournamentId, name: `Tournament ${tournamentId}`, teams, matches });
      } else {
        const error = await response.json();
        alert(`Error starting match: ${error.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Failed to start match:', error);
      alert('Network error: Failed to start match. Please try again.');
    }
  };

  const handleStartTournament = async () => {
    if (!showManagementActions) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/tournaments/${tournamentId}/status`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ status: 'In_Progress' })
      });

      if (response.ok) {
        setTournamentStatus('In_Progress');
      } else {
        const error = await response.json();
        alert(`Error starting tournament: ${error.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Failed to start tournament:', error);
      alert('Network error: Failed to start tournament. Please try again.');
    }
  };

  const getTop4Teams = () => {
    if (!tournament) return [];
    return tournament.teams
      .filter(t => t.final_place && t.final_place <= 4)
      .sort((a, b) => (a.final_place || 999) - (b.final_place || 999));
  };

  const calculatePayout = (place: number, totalParticipants: number, isUndefeated: boolean = false) => {
    const totalPot = 5 * totalParticipants;
    let secondPlace, firstPlace;
    
    if (totalPot < 60) {
      secondPlace = totalPot > 10 ? 10 : 0;
      firstPlace = totalPot - secondPlace;
    } else {
      secondPlace = Math.min(40, totalPot - 40);
      firstPlace = totalPot - secondPlace;
    }
    
    if (place === 1) {
      const acePayout = isUndefeated && tournamentData ? (tournamentData.ace_pot_payout || 0) : 0;
      return firstPlace + acePayout;
    }
    if (place === 2) return secondPlace;
    return 0;
  };

  const isTeamUndefeated = (teamId: number): boolean => {
    if (!tournament) return false;
    
    const teamMatches = tournament.matches.filter(m => 
      (m.team1_id === teamId || m.team2_id === teamId) && 
      m.match_status === 'Completed' && 
      m.team2_id !== null
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
                  {getTeamDisplayName(match.team1_id)} vs {getTeamDisplayName(match.team2_id)}
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
      
      <div className={`tournament-content ${matchesInProgress.length > 0 ? 'with-matches-in-progress' : ''}`} style={{ position: 'relative' }}>
        {showManagementActions && tournamentStatus === 'Scheduled' && currentUser?.role !== 'Admin' && (
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
        
        {showManagementActions && currentUser?.role === 'Admin' && (
          <div className="admin-match-creation">
            <h3>Create New Match</h3>
            <div className="match-form">
              <div className="form-row">
                <label>Stage Type:</label>
                <select value={newMatchData.stage_type} onChange={(e) => setNewMatchData({...newMatchData, stage_type: e.target.value})}>
                  <option value="Group_A">Group A</option>
                  <option value="Group_B">Group B</option>
                  <option value="Finals">Finals</option>
                </select>
              </div>
              <div className="form-row">
                <label>Round Type:</label>
                <select value={newMatchData.round_type} onChange={(e) => setNewMatchData({...newMatchData, round_type: e.target.value})}>
                  <option value="Winners">Winners</option>
                  <option value="Losers">Losers</option>
                  <option value="Championship">Championship</option>
                </select>
              </div>
              <div className="form-row">
                <label>Round Number:</label>
                <input type="number" value={newMatchData.round_number} onChange={(e) => setNewMatchData({...newMatchData, round_number: parseInt(e.target.value)})} />
              </div>
              <div className="form-row">
                <label>Position in Round:</label>
                <input type="number" value={newMatchData.position_in_round} onChange={(e) => setNewMatchData({...newMatchData, position_in_round: parseInt(e.target.value)})} />
              </div>
              <button onClick={handleCreateMatch} className="create-match-button">Create Match</button>
            </div>
          </div>
        )}
        
        {tournamentStatus === 'Completed' && showCompletionOverlay && (
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
                      <div className="team-name">{getTeamDisplayName(team.team_id)}</div>
                      {isUndefeated && team.final_place === 1 && <div className="ace-stamp">ACE</div>}
                      <div className="award">{getAward(team.final_place || 0, payout)}</div>
                    </div>
                  );
                })}
              </div>
              <button className="close-overlay-button" onClick={() => setShowCompletionOverlay(false)}>
                Close
              </button>
            </div>
          </div>
        )}
        
        <div className="brackets-container">
          <div className="main-brackets">
            {winnersMatches.length > 0 && (
              <Bracket 
                matches={winnersMatches}
                allMatches={tournament.matches}
                teams={tournament.teams}
                players={[]}
                title="Winners Bracket"
                onScoreMatch={showManagementActions && tournamentStatus === 'In_Progress' ? handleScoreMatch : undefined}
                onStartMatch={showManagementActions && tournamentStatus === 'In_Progress' ? handleStartMatch : undefined}
                currentUser={currentUser}
                tournamentId={tournamentId}
              />
            )}
            {losersMatches.length > 0 && (
              <Bracket 
                matches={losersMatches}
                allMatches={tournament.matches}
                teams={tournament.teams}
                players={[]}
                title="Losers Bracket"
                onScoreMatch={showManagementActions && tournamentStatus === 'In_Progress' ? handleScoreMatch : undefined}
                onStartMatch={showManagementActions && tournamentStatus === 'In_Progress' ? handleStartMatch : undefined}
                currentUser={currentUser}
                tournamentId={tournamentId}
              />
            )}
          </div>
          {championshipMatches.filter(m => m.team1_id && m.team2_id).length > 0 && (
            <div className="championship-section">
              <Bracket 
                matches={championshipMatches}
                allMatches={tournament.matches}
                teams={tournament.teams}
                players={[]}
                title="🏆 Championship"
                onScoreMatch={showManagementActions && tournamentStatus === 'In_Progress' ? handleScoreMatch : undefined}
                onStartMatch={showManagementActions && tournamentStatus === 'In_Progress' ? handleStartMatch : undefined}
                currentUser={currentUser}
                tournamentId={tournamentId}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default UnifiedTournamentView;
