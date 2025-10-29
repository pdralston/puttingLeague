import React, { useState } from 'react';
import { Player } from '../types/player';

interface PlayerRegistrationProps {
  onPlayerAdded: (player: Player) => void;
}

const PlayerRegistration: React.FC<PlayerRegistrationProps> = ({ onPlayerAdded }) => {
  const [name, setName] = useState('');
  const [nickname, setNickname] = useState('');
  const [division, setDivision] = useState<'Pro' | 'Am' | 'Junior'>('Am');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    setLoading(true);
    try {
      const response = await fetch('http://localhost:5000/api/players', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          player_name: name.trim(),
          nickname: nickname.trim() || null,
          division
        })
      });

      if (response.ok) {
        const result = await response.json();
        if (result.created && result.created.length > 0) {
          onPlayerAdded(result.created[0]);
          setName('');
          setNickname('');
          setDivision('Am');
        }
      }
    } catch (error) {
      console.error('Failed to register player:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="player-registration">
      <h3>Register Player</h3>
      <input
        type="text"
        placeholder="Player Name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        required
      />
      <input
        type="text"
        placeholder="Nickname (optional)"
        value={nickname}
        onChange={(e) => setNickname(e.target.value)}
      />
      <select value={division} onChange={(e) => setDivision(e.target.value as 'Pro' | 'Am' | 'Junior')}>
        <option value="Am">Amateur</option>
        <option value="Pro">Professional</option>
        <option value="Junior">Junior</option>
      </select>
      <button type="submit" disabled={loading || !name.trim()}>
        {loading ? 'Adding...' : 'Add Player'}
      </button>
    </form>
  );
};

export default PlayerRegistration;
