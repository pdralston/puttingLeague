import React, { useState, useEffect } from 'react';
import PlayerRegistration from './PlayerRegistration';
import PlayerList from './PlayerList';
import { Player } from '../types/player';

const PlayerManager: React.FC = () => {
  const [players, setPlayers] = useState<Player[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);

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

  const handlePlayerAdded = (newPlayer: Player) => {
    setPlayers(prev => [...prev, newPlayer]);
    setShowAddForm(false);
  };

  if (loading) return <div className="loading">Loading players...</div>;

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
      
      <PlayerList players={players} />
    </div>
  );
};

export default PlayerManager;
