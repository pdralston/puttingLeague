import React, { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL } from '../config/api';
import { Match, Team } from '../types/tournament';
import './TournamentEdit.css';

interface TournamentEditProps {
  tournamentId: number;
  onBack: () => void;
}

const TournamentEdit: React.FC<TournamentEditProps> = ({ tournamentId, onBack }) => {
  const [matches, setMatches] = useState<Match[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [selectedMatch, setSelectedMatch] = useState<Match | null>(null);
  const [editMode, setEditMode] = useState<'teams' | 'progression' | 'add'>('teams');
  const [loading, setLoading] = useState(true);

  // Form states
  const [team1Id, setTeam1Id] = useState<number | null>(null);
  const [team2Id, setTeam2Id] = useState<number | null>(null);
  const [winnerAdvancesTo, setWinnerAdvancesTo] = useState<number | null>(null);
  const [loserAdvancesTo, setLoserAdvancesTo] = useState<number | null>(null);

  // Add match form
  const [newMatch, setNewMatch] = useState({
    stage_type: 'Finals' as 'Group_A' | 'Group_B' | 'Finals',
    round_type: 'Winners' as 'Winners' | 'Losers' | 'Championship',
    round_number: 1,
    position_in_round: 1,
    stage_match_number: 1,
    match_order: 1,
    station_assignment: 1
  });

  useEffect(() => {
    fetchData();
  }, [tournamentId]);

  const fetchData = useCallback(async () => {
    try {
      const [matchesRes, teamsRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/tournaments/${tournamentId}/matches`, { credentials: 'include' }),
        fetch(`${API_BASE_URL}/api/tournaments/${tournamentId}/teams`, { credentials: 'include' })
      ]);
      
      const matchesData = await matchesRes.json();
      const teamsData = await teamsRes.json();
      
      setMatches(matchesData);
      setTeams(teamsData);
    } catch (error) {
      console.error('Failed to fetch data:', error);
    } finally {
      setLoading(false);
    }
  }, [tournamentId]);

  const handleMatchSelect = (match: Match) => {
    setSelectedMatch(match);
    setTeam1Id(match.team1_id ?? null);
    setTeam2Id(match.team2_id ?? null);
    setWinnerAdvancesTo(match.winner_advances_to_match_id ?? null);
    setLoserAdvancesTo(match.loser_advances_to_match_id ?? null);
  };

  const updateMatchTeams = async () => {
    if (!selectedMatch) return;
    
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/tournaments/${tournamentId}/edit/match/${selectedMatch.match_id}/teams`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ team1_id: team1Id, team2_id: team2Id })
        }
      );
      
      if (response.ok) {
        alert('Teams updated successfully');
        fetchData();
      }
    } catch (error) {
      console.error('Failed to update teams:', error);
    }
  };

  const updateMatchProgression = async () => {
    if (!selectedMatch) return;
    
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/tournaments/${tournamentId}/edit/match/${selectedMatch.match_id}/progression`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({
            winner_advances_to_match_id: winnerAdvancesTo,
            loser_advances_to_match_id: loserAdvancesTo
          })
        }
      );
      
      if (response.ok) {
        alert('Progression updated successfully');
        fetchData();
      }
    } catch (error) {
      console.error('Failed to update progression:', error);
    }
  };

  const addNewMatch = async () => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/tournaments/${tournamentId}/edit/matches`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify(newMatch)
        }
      );
      
      if (response.ok) {
        alert('Match added successfully');
        fetchData();
        setNewMatch({
          stage_type: 'Finals',
          round_type: 'Winners',
          round_number: 1,
          position_in_round: 1,
          stage_match_number: 1,
          match_order: 1,
          station_assignment: 1
        });
      }
    } catch (error) {
      console.error('Failed to add match:', error);
    }
  };

  const getTeamName = (teamId: number | null | undefined) => {
    if (!teamId) return 'TBD';
    const team = teams.find(t => t.team_id === teamId);
    return team ? `${team.player1_name}${team.player2_name ? ` / ${team.player2_name}` : ''}` : 'Unknown';
  };

  if (loading) return <div>Loading...</div>;

  return (
    <div className="tournament-edit">
      <div className="header">
        <button onClick={onBack}>← Back</button>
        <h2>Edit Tournament {tournamentId}</h2>
      </div>

      <div className="edit-tabs">
        <button 
          className={editMode === 'teams' ? 'active' : ''}
          onClick={() => setEditMode('teams')}
        >
          Edit Teams
        </button>
        <button 
          className={editMode === 'progression' ? 'active' : ''}
          onClick={() => setEditMode('progression')}
        >
          Edit Progression
        </button>
        <button 
          className={editMode === 'add' ? 'active' : ''}
          onClick={() => setEditMode('add')}
        >
          Add Match
        </button>
      </div>

      <div className="content">
        <div className="matches-list">
          <h3>Matches</h3>
          {matches.map(match => (
            <div 
              key={match.match_id}
              className={`match-item ${selectedMatch?.match_id === match.match_id ? 'selected' : ''}`}
              onClick={() => handleMatchSelect(match)}
            >
              <div>Match {match.match_order} - {match.round_type} R{match.round_number}</div>
              <div>{getTeamName(match.team1_id)} vs {getTeamName(match.team2_id)}</div>
            </div>
          ))}
        </div>

        <div className="edit-panel">
          {editMode === 'teams' && selectedMatch && (
            <div>
              <h3>Edit Teams for Match {selectedMatch.match_order}</h3>
              <div>
                <label>Team 1:</label>
                <select value={team1Id || ''} onChange={(e) => setTeam1Id(e.target.value ? Number(e.target.value) : null)}>
                  <option value="">Select Team</option>
                  {teams.map(team => (
                    <option key={team.team_id} value={team.team_id}>
                      {getTeamName(team.team_id)}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label>Team 2:</label>
                <select value={team2Id || ''} onChange={(e) => setTeam2Id(e.target.value ? Number(e.target.value) : null)}>
                  <option value="">Select Team</option>
                  {teams.map(team => (
                    <option key={team.team_id} value={team.team_id}>
                      {getTeamName(team.team_id)}
                    </option>
                  ))}
                </select>
              </div>
              <button onClick={updateMatchTeams}>Update Teams</button>
            </div>
          )}

          {editMode === 'progression' && selectedMatch && (
            <div>
              <h3>Edit Progression for Match {selectedMatch.match_order}</h3>
              <div>
                <label>Winner advances to match:</label>
                <select value={winnerAdvancesTo || ''} onChange={(e) => setWinnerAdvancesTo(e.target.value ? Number(e.target.value) : null)}>
                  <option value="">No advancement</option>
                  {matches.map(match => (
                    <option key={match.match_id} value={match.match_id}>
                      Match {match.match_order}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label>Loser advances to match:</label>
                <select value={loserAdvancesTo || ''} onChange={(e) => setLoserAdvancesTo(e.target.value ? Number(e.target.value) : null)}>
                  <option value="">No advancement</option>
                  {matches.map(match => (
                    <option key={match.match_id} value={match.match_id}>
                      Match {match.match_order}
                    </option>
                  ))}
                </select>
              </div>
              <button onClick={updateMatchProgression}>Update Progression</button>
            </div>
          )}

          {editMode === 'add' && (
            <div>
              <h3>Add New Match</h3>
              <div>
                <label>Stage Type:</label>
                <select value={newMatch.stage_type} onChange={(e) => setNewMatch({...newMatch, stage_type: e.target.value as any})}>
                  <option value="Group_A">Group A</option>
                  <option value="Group_B">Group B</option>
                  <option value="Finals">Finals</option>
                </select>
              </div>
              <div>
                <label>Round Type:</label>
                <select value={newMatch.round_type} onChange={(e) => setNewMatch({...newMatch, round_type: e.target.value as any})}>
                  <option value="Winners">Winners</option>
                  <option value="Losers">Losers</option>
                  <option value="Championship">Championship</option>
                </select>
              </div>
              <div>
                <label>Round Number:</label>
                <input type="number" value={newMatch.round_number} onChange={(e) => setNewMatch({...newMatch, round_number: Number(e.target.value)})} />
              </div>
              <div>
                <label>Position in Round:</label>
                <input type="number" value={newMatch.position_in_round} onChange={(e) => setNewMatch({...newMatch, position_in_round: Number(e.target.value)})} />
              </div>
              <div>
                <label>Stage Match Number:</label>
                <input type="number" value={newMatch.stage_match_number} onChange={(e) => setNewMatch({...newMatch, stage_match_number: Number(e.target.value)})} />
              </div>
              <div>
                <label>Match Order:</label>
                <input type="number" value={newMatch.match_order} onChange={(e) => setNewMatch({...newMatch, match_order: Number(e.target.value)})} />
              </div>
              <div>
                <label>Station:</label>
                <input type="number" min="1" max="6" value={newMatch.station_assignment} onChange={(e) => setNewMatch({...newMatch, station_assignment: Number(e.target.value)})} />
              </div>
              <button onClick={addNewMatch}>Add Match</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default TournamentEdit;
