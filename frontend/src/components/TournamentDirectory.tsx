import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config/api';

interface Tournament {
  tournament_id: number;
  tournament_date: string;
  status: string;
  total_teams?: number;
}

interface TournamentDirectoryProps {
  onTournamentSelect: (tournamentId: number) => void;
  onTournamentManage: (tournamentId: number) => void;
  onCreateTournament: () => void;
  userRole?: string;
}

const TournamentDirectory: React.FC<TournamentDirectoryProps> = ({ 
  onTournamentSelect, 
  onTournamentManage, 
  onCreateTournament,
  userRole = 'Viewer'
}) => {
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTournaments();
  }, []);

  const fetchTournaments = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/tournaments`);
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

  const handleDelete = async (tournamentId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this tournament? This will delete all matches, teams, and registrations.')) {
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/tournaments/${tournamentId}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        setTournaments(prev => prev.filter(t => t.tournament_id !== tournamentId));
      } else {
        alert('Failed to delete tournament');
      }
    } catch (error) {
      console.error('Failed to delete tournament:', error);
      alert('Failed to delete tournament');
    }
  };

  if (loading) return <div className="loading">Loading tournaments...</div>;

  return (
    <div className="tournament-directory">
      <div className="page-header">
        <h2>Tournaments</h2>
        {(userRole === 'Admin' || userRole === 'Director') && (
          <button className="create-tournament-button" onClick={onCreateTournament}>
            Create Tournament
          </button>
        )}
      </div>
      
      <div className="table-container">
        <table className="tournaments-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Status</th>
              <th>Teams</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {tournaments.map(tournament => (
              <tr key={tournament.tournament_id}>
                <td>{new Date(tournament.tournament_date).toLocaleDateString()}</td>
                <td>{tournament.status}</td>
                <td>{tournament.total_teams || 0}</td>
                <td>
                  <div className="action-buttons">
                    <button 
                      className="view-button"
                      onClick={() => onTournamentSelect(tournament.tournament_id)}
                    >
                      View
                    </button>
                    {(userRole === 'Admin' || userRole === 'Director') && (
                      <button 
                        className="manage-button"
                        onClick={() => onTournamentManage(tournament.tournament_id)}
                      >
                        Manage
                      </button>
                    )}
                    {userRole === 'Admin' && (
                      <button 
                        className="delete-button"
                        onClick={(e) => handleDelete(tournament.tournament_id, e)}
                      >
                        Delete
                      </button>
                    )}
                  </div>
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
