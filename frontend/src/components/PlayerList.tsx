import React, { useState } from 'react';
import { Player } from '../types/player';

interface PlayerListProps {
  players: Player[];
  onPlayerClick: (player: Player) => void;
}

const PlayerList: React.FC<PlayerListProps> = ({ players, onPlayerClick }) => {
  const [divisionFilter, setDivisionFilter] = useState<string>('All');

  // Filter players by division
  const filteredPlayers = divisionFilter === 'All' 
    ? players 
    : players.filter(p => p.division === divisionFilter);

  // Sort players alphabetically by name
  const sortedPlayers = filteredPlayers.sort((a, b) => 
    a.player_name.localeCompare(b.player_name)
  );

  // Calculate divisional rankings
  const getDivisionalRank = (player: Player): number => {
    const divisionPlayers = players
      .filter(p => p.division === player.division)
      .sort((a, b) => b.seasonal_points - a.seasonal_points);
    
    // Handle ties - players with same points get same rank
    let rank = 1;
    for (let i = 0; i < divisionPlayers.length; i++) {
      if (i > 0 && divisionPlayers[i].seasonal_points < divisionPlayers[i-1].seasonal_points) {
        rank = i + 1;
      }
      if (divisionPlayers[i].player_id === player.player_id) {
        return rank;
      }
    }
    
    return divisionPlayers.length + 1;
  };

  // Get CSS class for divisional leaders
  const getLeaderClass = (player: Player): string => {
    if (player.seasonal_points === 0) return '';
    const rank = getDivisionalRank(player);
    if (rank === 1) return 'division-leader-1st';
    if (rank === 2) return 'division-leader-2nd';
    if (rank === 3) return 'division-leader-3rd';
    return '';
  };

  // Get rank display
  const getRankDisplay = (player: Player): string => {
    if (player.seasonal_points === 0) return '';
    const rank = getDivisionalRank(player);
    if (rank === 1) return '👑';
    if (rank === 2) return '🥈';
    if (rank === 3) return '🥉';
    return '';
  };

  return (
    <div className="player-list-view">
      <div className="table-container">
        <table className="players-table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>Name</th>
              <th>
                <select 
                  value={divisionFilter} 
                  onChange={(e) => setDivisionFilter(e.target.value)}
                  style={{ background: 'transparent', border: 'none', color: '#000', fontWeight: 'bold' }}
                >
                  <option value="All">All Divisions</option>
                  <option value="Pro">Pro</option>
                  <option value="Am">Am</option>
                  <option value="Junior">Junior</option>
                </select>
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedPlayers.map(player => (
              <tr 
                key={player.player_id} 
                onClick={() => onPlayerClick(player)} 
                className={`clickable-row ${getLeaderClass(player)}`}
              >
                <td className="rank-cell">
                  {getRankDisplay(player)}
                </td>
                <td>
                  <div className="player-name">
                    {player.player_name}
                    {player.nickname && <span className="nickname">"{player.nickname}"</span>}
                  </div>
                </td>
                <td>{player.division}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {sortedPlayers.length === 0 && (
          <div className="empty-state">No players found.</div>
        )}
      </div>
    </div>
  );
};

export default PlayerList;
