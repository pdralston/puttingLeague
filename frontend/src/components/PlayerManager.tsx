import React, { useState, useEffect } from 'react';
import PlayerRegistration from './PlayerRegistration';
import PlayerList from './PlayerList';
import { Player } from '../types/player';

const PlayerManager: React.FC = () => {
  const [players, setPlayers] = useState<Player[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null);
  const [playerDetail, setPlayerDetail] = useState<any>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

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

  const getDivisionalRankSuffix = (player: Player): string => {
    const rank = getDivisionalRank(player);
    if (rank === 1) return '1st';
    if (rank === 2) return '2nd';
    if (rank === 3) return '3rd';
    return '';
  };

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

  const filteredPlayers = players.filter(player =>
    player.player_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (player.nickname && player.nickname.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const handlePlayerClick = async (player: Player) => {
    setSelectedPlayer(player);
    setLoadingDetail(true);
    try {
      const response = await fetch(`http://localhost:5000/api/players/${player.player_id}`);
      if (response.ok) {
        const data = await response.json();
        setPlayerDetail(data);
      }
    } catch (error) {
      console.error('Failed to fetch player details:', error);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handlePlayerAdded = (newPlayer: Player) => {
    setPlayers(prev => [...prev, newPlayer]);
    setShowAddForm(false);
  };

  if (loading) return <div className="loading">Loading players...</div>;

  if (selectedPlayer) {
    return (
      <div className="player-manager">
        <div className="back-button-container">
          <button className="back-button" onClick={() => {setSelectedPlayer(null); setPlayerDetail(null);}}>
            ← Back to Players
          </button>
        </div>
        <div className={`player-detail ${getDivisionalRank(selectedPlayer) <= 3 ? `division-leader-${getDivisionalRankSuffix(selectedPlayer)}` : ''}`}>
          <h2>
            {getDivisionalRank(selectedPlayer) === 1 && '👑 '}
            {getDivisionalRank(selectedPlayer) === 2 && '🥈 '}
            {getDivisionalRank(selectedPlayer) === 3 && '🥉 '}
            {selectedPlayer.player_name}
          </h2>
          {selectedPlayer.nickname && <p className="nickname">"{selectedPlayer.nickname}"</p>}
          <div className="player-stats">
            <div className="stat">
              <label>Division:</label>
              <span>{selectedPlayer.division}</span>
            </div>
            <div className="stat">
              <label>Seasonal Points:</label>
              <span>{selectedPlayer.seasonal_points}</span>
            </div>
            <div className="stat">
              <label>Seasonal Cash:</label>
              <span>${selectedPlayer.seasonal_cash}</span>
            </div>
          </div>
          
          {loadingDetail ? (
            <div className="loading">Loading tournament history...</div>
          ) : playerDetail && (
            <>
              <h3>Tournament History</h3>
              <div className="tournament-history">
                {playerDetail.tournament_history.length > 0 ? (
                  playerDetail.tournament_history.map((t: any) => (
                    <div key={t.tournament_id} className="tournament-entry">
                      <span>{t.tournament_date}</span>
                      <span>Status: {t.status}</span>
                      {t.final_place && <span>Place: {t.final_place}</span>}
                      {t.bought_ace_pot && <span>🎯 Ace Pot</span>}
                    </div>
                  ))
                ) : (
                  <p>No tournament history</p>
                )}
              </div>

              <h3>Teammate History</h3>
              <div className="teammate-history">
                {playerDetail.teammate_history.length > 0 ? (
                  playerDetail.teammate_history.map((tm: any) => (
                    <div key={tm.teammate_id} className="teammate-entry">
                      <span className="teammate-name">
                        {tm.teammate_name}
                        {tm.teammate_nickname && ` "${tm.teammate_nickname}"`}
                      </span>
                      <span>Paired: {tm.times_paired} times</span>
                      {tm.average_place && <span>Avg Place: {tm.average_place}</span>}
                    </div>
                  ))
                ) : (
                  <p>No teammate history</p>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="player-manager">
      <div className="page-header">
        <h2>Players</h2>
        <button 
          className="add-button"
          onClick={() => setShowAddForm(!showAddForm)}
        >
          {showAddForm ? 'Cancel' : 'Add Player'}
        </button>
      </div>
      
      {showAddForm && (
        <PlayerRegistration onPlayerAdded={handlePlayerAdded} />
      )}
      
      <div className="search-section">
        <input
          type="text"
          placeholder="Search players..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="search-input"
        />
      </div>
      
      <PlayerList players={filteredPlayers} onPlayerClick={handlePlayerClick} />
    </div>
  );
};

export default PlayerManager;
