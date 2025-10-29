import React from 'react';
import { Player } from '../types/player';

interface PlayerListProps {
  players: Player[];
}

const PlayerList: React.FC<PlayerListProps> = ({ players }) => {
  return (
    <div className="player-list">
      <div className="table-container">
        <table className="players-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Division</th>
              <th>Points</th>
              <th>Cash</th>
            </tr>
          </thead>
          <tbody>
            {players.map(player => (
              <tr key={player.player_id}>
                <td>
                  <div className="player-name">
                    {player.player_name}
                    {player.nickname && <span className="nickname">"{player.nickname}"</span>}
                  </div>
                </td>
                <td>{player.division}</td>
                <td>{player.seasonal_points}</td>
                <td>${player.seasonal_cash}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {players.length === 0 && (
          <div className="empty-state">No players registered yet.</div>
        )}
      </div>
    </div>
  );
};

export default PlayerList;
