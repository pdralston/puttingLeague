import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config/api';
import { Player } from '../types/player';

interface TournamentCreationProps {
  onBack: () => void;
  onTournamentCreated: () => void;
}

interface SelectedPlayer extends Player {
  bought_ace_pot: boolean;
}

const TournamentCreation: React.FC<TournamentCreationProps> = ({ onBack, onTournamentCreated }) => {
  const [availablePlayers, setAvailablePlayers] = useState<Player[]>([]);
  const [selectedPlayers, setSelectedPlayers] = useState<SelectedPlayer[]>([]);
  const [tournamentDate, setTournamentDate] = useState(new Date().toISOString().split('T')[0]);
  const [loading, setLoading] = useState(false);
  const [showNewPlayerForm, setShowNewPlayerForm] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [newPlayer, setNewPlayer] = useState({
    player_name: '',
    nickname: '',
    division: 'Am' as 'Pro' | 'Am' | 'Junior'
  });

  useEffect(() => {
    fetchPlayers();
  }, []);

  const fetchPlayers = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/players`);
      if (response.ok) {
        const data = await response.json();
        setAvailablePlayers(data);
      }
    } catch (error) {
      console.error('Failed to fetch players:', error);
    }
  };

  const filteredPlayers = availablePlayers.filter(player =>
    !selectedPlayers.find(p => p.player_id === player.player_id) &&
    (player.player_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (player.nickname && player.nickname.toLowerCase().includes(searchTerm.toLowerCase())))
  );

  const addPlayer = (player: Player) => {
    if (!selectedPlayers.find(p => p.player_id === player.player_id)) {
      setSelectedPlayers([...selectedPlayers, { ...player, bought_ace_pot: false }]);
    }
  };

  const removePlayer = (playerId: number) => {
    setSelectedPlayers(selectedPlayers.filter(p => p.player_id !== playerId));
  };

  const toggleAcePot = (playerId: number) => {
    setSelectedPlayers(selectedPlayers.map(p => 
      p.player_id === playerId ? { ...p, bought_ace_pot: !p.bought_ace_pot } : p
    ));
  };

  const handleNewPlayerSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    const duplicate = availablePlayers.find(p => 
      p.player_name.toLowerCase() === newPlayer.player_name.toLowerCase()
    );
    if (duplicate) {
      alert('Player already exists in the league');
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/players`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newPlayer)
      });

      if (response.ok) {
        const result = await response.json();
        const createdPlayer = result.created[0];
        setAvailablePlayers([...availablePlayers, createdPlayer]);
        addPlayer(createdPlayer);
        setNewPlayer({ player_name: '', nickname: '', division: 'Am' });
        setShowNewPlayerForm(false);
      }
    } catch (error) {
      console.error('Failed to create player:', error);
    }
  };

  const createTournament = async () => {
    if (selectedPlayers.length < 2) {
      alert('Need at least 2 players to create a tournament');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/tournaments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tournament_date: tournamentDate,
          players: selectedPlayers.map(p => ({
            player_id: p.player_id,
            bought_ace_pot: p.bought_ace_pot
          }))
        })
      });

      if (response.ok) {
        const tournamentData = await response.json();
        
        // Generate matches for the tournament
        const matchesResponse = await fetch(`${API_BASE_URL}/api/tournaments/${tournamentData.tournament_id}/generate-matches`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });

        if (matchesResponse.ok) {
          onTournamentCreated();
        } else {
          alert('Tournament created but failed to generate matches');
        }
      } else {
        alert('Failed to create tournament');
      }
    } catch (error) {
      console.error('Failed to create tournament:', error);
      alert('Failed to create tournament');
    } finally {
      setLoading(false);
    }
  };

  const acePotCount = selectedPlayers.filter(p => p.bought_ace_pot).length;

  return (
    <div className="tournament-creation">
      <div className="back-button-container">
        <button className="back-button" onClick={onBack}>← Back</button>
      </div>

      <div className="page-header">
        <h2>Create Tournament</h2>
      </div>

      <div className="creation-form">
        <div className="form-section">
          <label>Tournament Date:</label>
          <input
            type="date"
            value={tournamentDate}
            onChange={(e) => setTournamentDate(e.target.value)}
          />
        </div>

        <div className="players-section">
          <div className="available-players">
            <h3>Available Players</h3>
            <input
              type="text"
              placeholder="Search players..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="search-input"
            />
            <div className="player-list">
              {filteredPlayers.map(player => (
                <div key={player.player_id} className="player-item">
                  <span>{player.player_name} ({player.division})</span>
                  <button onClick={() => addPlayer(player)}>Add</button>
                </div>
              ))}
            </div>
            <button 
              className="new-player-button"
              onClick={() => setShowNewPlayerForm(true)}
            >
              Register New Player
            </button>
          </div>

          <div className="selected-players">
            <h3>Tournament Players ({selectedPlayers.length})</h3>
            <div className="ace-pot-summary">Ace Pot Buy-ins: {acePotCount} (${acePotCount}.00)</div>
            <div className="player-list">
              {selectedPlayers.map(player => (
                <div key={player.player_id} className="player-item selected">
                  <span>{player.player_name} ({player.division})</span>
                  <div className="player-controls">
                    <label className="ace-pot-checkbox">
                      <input
                        type="checkbox"
                        checked={player.bought_ace_pot}
                        onChange={() => toggleAcePot(player.player_id)}
                      />
                      Ace Pot
                    </label>
                    <button onClick={() => removePlayer(player.player_id)}>Remove</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {showNewPlayerForm && (
          <div className="new-player-form">
            <h3>Register New Player</h3>
            <form onSubmit={handleNewPlayerSubmit}>
              <input
                type="text"
                placeholder="Player Name"
                value={newPlayer.player_name}
                onChange={(e) => setNewPlayer({...newPlayer, player_name: e.target.value})}
                required
              />
              <input
                type="text"
                placeholder="Nickname (optional)"
                value={newPlayer.nickname}
                onChange={(e) => setNewPlayer({...newPlayer, nickname: e.target.value})}
              />
              <select
                value={newPlayer.division}
                onChange={(e) => setNewPlayer({...newPlayer, division: e.target.value as 'Pro' | 'Am' | 'Junior'})}
              >
                <option value="Pro">Pro</option>
                <option value="Am">Am</option>
                <option value="Junior">Junior</option>
              </select>
              <div className="form-buttons">
                <button type="submit">Add Player</button>
                <button type="button" onClick={() => setShowNewPlayerForm(false)}>Cancel</button>
              </div>
            </form>
          </div>
        )}

        <div className="create-section">
          <button 
            className="create-tournament-button"
            onClick={createTournament}
            disabled={loading || selectedPlayers.length < 2}
          >
            {loading ? 'Creating...' : 'Create Tournament'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default TournamentCreation;
