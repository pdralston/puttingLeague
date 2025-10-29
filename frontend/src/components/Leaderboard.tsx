import React, { useState, useEffect } from 'react';
import { Player } from '../types/player';

const Leaderboard: React.FC = () => {
  const [players, setPlayers] = useState<Player[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerms, setSearchTerms] = useState<Record<string, string>>({
    Pro: '',
    Am: '',
    Junior: ''
  });

  useEffect(() => {
    fetchPlayers();
  }, []);

  const fetchPlayers = async () => {
    try {
      const response = await fetch('http://localhost:5000/api/players');
      if (response.ok) {
        const data = await response.json();
        setPlayers(data);
      }
    } catch (error) {
      console.error('Failed to fetch players:', error);
    } finally {
      setLoading(false);
    }
  };

  const groupedPlayers = players.reduce((acc, player) => {
    if (!acc[player.division]) acc[player.division] = [];
    acc[player.division].push(player);
    return acc;
  }, {} as Record<string, Player[]>);

  // Sort each division by points (descending) and filter by search
  const getFilteredPlayers = (division: string) => {
    const divisionPlayers = groupedPlayers[division] || [];
    const searchTerm = searchTerms[division].toLowerCase();
    
    return divisionPlayers
      .filter(player => {
        const name = (player.nickname || player.player_name).toLowerCase();
        return name.includes(searchTerm);
      })
      .sort((a, b) => b.seasonal_points - a.seasonal_points);
  };

  const handleSearchChange = (division: string, value: string) => {
    setSearchTerms(prev => ({ ...prev, [division]: value }));
  };

  if (loading) return <div className="loading">Loading leaderboard...</div>;

  return (
    <div className="leaderboard">
      <div className="page-header">
        <h2>Leaderboard</h2>
      </div>
      
      <div className="divisions-container">
        {['Pro', 'Am', 'Junior'].map(division => {
          const divisionPlayers = groupedPlayers[division] || [];
          if (divisionPlayers.length === 0) return null;
          
          const filteredPlayers = getFilteredPlayers(division);
          
          return (
            <div key={division} className="division-column">
              <h3>{division} Division</h3>
              <input
                type="text"
                placeholder="Search players..."
                value={searchTerms[division]}
                onChange={(e) => handleSearchChange(division, e.target.value)}
                className="search-input"
              />
              <div className="table-scroll">
                <table className="leaderboard-table">
                  <thead>
                    <tr>
                      <th>Rank</th>
                      <th>Player</th>
                      <th>Points</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredPlayers.map((player, index) => (
                      <tr key={player.player_id}>
                        <td>{index + 1}</td>
                        <td>{player.nickname || player.player_name}</td>
                        <td>{player.seasonal_points}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          );
        })}
      </div>
      
      {players.length === 0 && (
        <div className="empty-state">No players registered yet.</div>
      )}
    </div>
  );
};

export default Leaderboard;
