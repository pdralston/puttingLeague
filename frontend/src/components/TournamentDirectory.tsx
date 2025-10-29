import React, { useState, useEffect } from 'react';

interface Tournament {
  tournament_id: number;
  tournament_date: string;
  status: string;
  total_teams?: number;
}

interface TournamentDirectoryProps {
  onTournamentSelect: (tournamentId: number) => void;
}

const TournamentDirectory: React.FC<TournamentDirectoryProps> = ({ onTournamentSelect }) => {
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTournaments();
  }, []);

  const fetchTournaments = async () => {
    try {
      const response = await fetch('http://localhost:5000/api/tournaments');
      if (response.ok) {
        const data = await response.json();
        setTournaments(data);
      }
    } catch (error) {
      console.error('Failed to fetch tournaments:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="loading">Loading tournaments...</div>;

  return (
    <div className="tournament-directory">
      <div className="page-header">
        <h2>Tournaments</h2>
      </div>
      
      <div className="table-container">
        <table className="tournaments-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Status</th>
              <th>Teams</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {tournaments.map(tournament => (
              <tr key={tournament.tournament_id}>
                <td>{new Date(tournament.tournament_date).toLocaleDateString()}</td>
                <td>{tournament.status}</td>
                <td>{tournament.total_teams || 0}</td>
                <td>
                  <button 
                    className="view-button"
                    onClick={() => onTournamentSelect(tournament.tournament_id)}
                  >
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {tournaments.length === 0 && (
          <div className="empty-state">No tournaments found.</div>
        )}
      </div>
    </div>
  );
};

export default TournamentDirectory;
