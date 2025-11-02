import React, { useState, useEffect } from 'react';
import PlayerRegistration from './PlayerRegistration';
import PlayerList from './PlayerList';
import { Player } from '../types/player';
import { API_BASE_URL } from '../config/api';

interface PlayerManagerProps {
  userRole?: string;
}

const PlayerManager: React.FC<PlayerManagerProps> = ({ userRole = 'Viewer' }) => {
  const [players, setPlayers] = useState<Player[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null);
  const [playerDetail, setPlayerDetail] = useState<any>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [showBulkRegister, setShowBulkRegister] = useState(false);
  const [csvData, setCsvData] = useState('');
  const [bulkLoading, setBulkLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [editingPlayer, setEditingPlayer] = useState<Player | null>(null);
  const [editForm, setEditForm] = useState({ player_name: '', nickname: '', division: '' });

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
      const response = await fetch(`${API_BASE_URL}/api/players`);
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

  const handleEditPlayer = (player: Player) => {
    setEditingPlayer(player);
    setEditForm({
      player_name: player.player_name,
      nickname: player.nickname || '',
      division: player.division
    });
  };

  const handleUpdatePlayer = async () => {
    if (!editingPlayer) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/players/${editingPlayer.player_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editForm)
      });
      
      if (response.ok) {
        await fetchPlayers();
        setEditingPlayer(null);
        setEditForm({ player_name: '', nickname: '', division: '' });
      }
    } catch (error) {
      console.error('Failed to update player:', error);
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
      const response = await fetch(`${API_BASE_URL}/api/players/${player.player_id}`);
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

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      const reader = new FileReader();
      reader.onload = (e) => {
        setCsvData(e.target?.result as string);
      };
      reader.readAsText(file);
    }
  };

  const handleBulkRegister = async () => {
    if (!csvData.trim()) return;
    
    setBulkLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/players/batch-csv`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ csv_data: csvData })
      });
      
      if (response.ok) {
        const result = await response.json();
        setPlayers(prev => [...prev, ...result.created]);
        setShowBulkRegister(false);
        setCsvData('');
        setSelectedFile(null);
        if (result.errors?.length > 0) {
          alert(`Registered ${result.created.length} players. Errors: ${result.errors.join(', ')}`);
        }
      }
    } catch (error) {
      console.error('Bulk registration failed:', error);
    } finally {
      setBulkLoading(false);
    }
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
        <div className={`player-detail ${selectedPlayer.seasonal_points > 0 && getDivisionalRank(selectedPlayer) <= 3 ? `division-leader-${getDivisionalRankSuffix(selectedPlayer)}` : ''}`}>
          <h2>
            {selectedPlayer.seasonal_points > 0 && getDivisionalRank(selectedPlayer) === 1 && '👑 '}
            {selectedPlayer.seasonal_points > 0 && getDivisionalRank(selectedPlayer) === 2 && '🥈 '}
            {selectedPlayer.seasonal_points > 0 && getDivisionalRank(selectedPlayer) === 3 && '🥉 '}
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
        {(userRole === 'Admin' || userRole === 'Director') && (
          <div className="header-buttons">
            <button 
              className="add-button"
              onClick={() => setShowAddForm(!showAddForm)}
            >
              {showAddForm ? 'Cancel' : 'Add Player'}
            </button>
            <button 
              className="add-button"
              onClick={() => setShowBulkRegister(!showBulkRegister)}
            >
              Add Players
            </button>
          </div>
        )}
      </div>
      
      {showAddForm && (
        <PlayerRegistration onPlayerAdded={handlePlayerAdded} />
      )}
      
      {showBulkRegister && (
        <div className="bulk-register-modal">
          <h3>Bulk Register Players</h3>
          <p>Select a CSV file with headers: player_name,nickname,division</p>
          <input
            type="file"
            accept=".csv"
            onChange={handleFileSelect}
            style={{ marginBottom: '10px' }}
          />
          {selectedFile && (
            <p>Selected: {selectedFile.name}</p>
          )}
          {csvData && (
            <div>
              <h4>Preview:</h4>
              <pre style={{ background: '#f8f9fa', padding: '10px', fontSize: '12px', maxHeight: '200px', overflow: 'auto' }}>
                {csvData.split('\n').slice(0, 5).join('\n')}
                {csvData.split('\n').length > 5 && '\n...'}
              </pre>
            </div>
          )}
          <div>
            <button onClick={handleBulkRegister} disabled={bulkLoading || !csvData}>
              {bulkLoading ? 'Registering...' : 'Register Players'}
            </button>
            <button onClick={() => {setShowBulkRegister(false); setCsvData(''); setSelectedFile(null);}}>Cancel</button>
          </div>
        </div>
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
      
      <PlayerList 
        players={filteredPlayers} 
        onPlayerClick={handlePlayerClick}
        onEditPlayer={(userRole === 'Admin' || userRole === 'Director') ? handleEditPlayer : undefined}
      />
      
      {editingPlayer && (
        <div className="edit-modal-overlay">
          <div className="edit-modal">
            <h3>Edit Player</h3>
            <div className="form-group">
              <label>Player Name:</label>
              <input
                type="text"
                value={editForm.player_name}
                onChange={(e) => setEditForm({...editForm, player_name: e.target.value})}
              />
            </div>
            <div className="form-group">
              <label>Nickname:</label>
              <input
                type="text"
                value={editForm.nickname}
                onChange={(e) => setEditForm({...editForm, nickname: e.target.value})}
              />
            </div>
            <div className="form-group">
              <label>Division:</label>
              <select
                value={editForm.division}
                onChange={(e) => setEditForm({...editForm, division: e.target.value})}
              >
                <option value="Am">Am</option>
                <option value="Pro">Pro</option>
                <option value="Junior">Junior</option>
              </select>
            </div>
            <div className="modal-buttons">
              <button onClick={() => setEditingPlayer(null)}>Cancel</button>
              <button onClick={handleUpdatePlayer}>Update</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PlayerManager;
