import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config/api';
import AdminAudit from './AdminAudit';
import TournamentEdit from './TournamentEdit';
import './Admin.css';

interface User {
  user_id: number;
  username: string;
  role: string;
  created_at: string;
}

interface Tournament {
  tournament_id: number;
  tournament_date: string;
  status: string;
  total_teams: number;
}

interface AdminProps {
  currentUser: { user_id: number; username: string; role: string };
}

const PAYOUT_DEFAULTS_KEY = 'dgputt_payout_defaults';
const FACTORY_PAYOUT_DEFAULTS = { mode: 'fixed' as 'fixed' | 'percentage', second_place_value: 20, buy_in_per_player: 5 };

export function loadPayoutDefaults() {
  try {
    const saved = localStorage.getItem(PAYOUT_DEFAULTS_KEY);
    return saved ? { ...FACTORY_PAYOUT_DEFAULTS, ...JSON.parse(saved) } : { ...FACTORY_PAYOUT_DEFAULTS };
  } catch {
    return { ...FACTORY_PAYOUT_DEFAULTS };
  }
}

const Admin: React.FC<AdminProps> = ({ currentUser }) => {
  const [activeAdminTab, setActiveAdminTab] = useState<'users' | 'audit' | 'tournaments' | 'payout'>('users');
  const [users, setUsers] = useState<User[]>([]);
  const [tournaments, setTournaments] = useState<Tournament[]>([]);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [formData, setFormData] = useState({ username: '', password: '', role: 'Director' });
  const [selectedTournamentId, setSelectedTournamentId] = useState<number | null>(null);

  // Payout settings state
  const [payoutSettings, setPayoutSettings] = useState(() => loadPayoutDefaults());
  const isCustomPayout = JSON.stringify(loadPayoutDefaults()) !== JSON.stringify(FACTORY_PAYOUT_DEFAULTS);

  // Archive state
  type ArchiveStep = 'idle' | 'warning' | 'form';
  const [archiveStep, setArchiveStep] = useState<ArchiveStep>('idle');
  const [archiveSeasonName, setArchiveSeasonName] = useState('');
  const [archivePreview, setArchivePreview] = useState<{
    start_date: string | null;
    end_date: string | null;
    event_count: number;
    unique_participants: number;
    total_participants: number;
  } | null>(null);
  const [archiveLoading, setArchiveLoading] = useState(false);

  const openArchiveWarning = () => setArchiveStep('warning');

  const proceedToArchiveForm = async () => {
    setArchiveLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/archive/preview`, { credentials: 'include' });
      if (res.ok) setArchivePreview(await res.json());
    } catch (e) {
      console.error('Failed to load archive preview', e);
    } finally {
      setArchiveLoading(false);
    }
    setArchiveStep('form');
  };

  const cancelArchive = () => {
    setArchiveStep('idle');
    setArchiveSeasonName('');
    setArchivePreview(null);
  };

  const performArchive = async () => {
    if (!archiveSeasonName.trim()) return;
    setArchiveLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/archive`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ season_name: archiveSeasonName.trim() })
      });
      if (res.ok) {
        alert(`Season "${archiveSeasonName.trim()}" archived successfully.`);
        cancelArchive();
      } else {
        const err = await res.json();
        alert(err.error || 'Archive failed.');
      }
    } catch (e) {
      console.error('Archive error', e);
      alert('Archive failed.');
    } finally {
      setArchiveLoading(false);
    }
  };

  const savePayoutDefaults = () => {
    localStorage.setItem(PAYOUT_DEFAULTS_KEY, JSON.stringify(payoutSettings));
    alert('Payout settings saved as default.');
  };

  const resetPayoutDefaults = () => {
    localStorage.removeItem(PAYOUT_DEFAULTS_KEY);
    setPayoutSettings({ ...FACTORY_PAYOUT_DEFAULTS });
  };

  useEffect(() => {
    if (currentUser.role === 'Admin') {
      fetchUsers();
    }
    if (currentUser.role === 'Admin' || currentUser.role === 'Director') {
      fetchTournaments();
    }
  }, [currentUser.role]);

  const fetchUsers = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/users`, {
        credentials: 'include'
      });
      if (response.ok) {
        const data = await response.json();
        setUsers(data);
      }
    } catch (error) {
      console.error('Failed to fetch users:', error);
    }
  };

  const fetchTournaments = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/tournaments`, {
        credentials: 'include'
      });
      if (response.ok) {
        const data = await response.json();
        setTournaments(data.filter((t: Tournament) => t.status === 'In_Progress'));
      }
    } catch (error) {
      console.error('Failed to fetch tournaments:', error);
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(formData)
      });
      
      if (response.ok) {
        setFormData({ username: '', password: '', role: 'Director' });
        setShowCreateForm(false);
        fetchUsers();
      } else {
        const error = await response.json();
        alert(error.error);
      }
    } catch (error) {
      console.error('Failed to create user:', error);
    }
  };

  const handleUpdateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingUser) return;

    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/users/${editingUser.user_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(formData)
      });
      
      if (response.ok) {
        setEditingUser(null);
        setFormData({ username: '', password: '', role: 'Director' });
        fetchUsers();
      } else {
        const error = await response.json();
        alert(error.error);
      }
    } catch (error) {
      console.error('Failed to update user:', error);
    }
  };

  const handleDeleteUser = async (userId: number) => {
    if (!window.confirm('Are you sure you want to delete this user?')) return;

    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/users/${userId}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      
      if (response.ok) {
        fetchUsers();
      } else {
        const error = await response.json();
        alert(error.error);
      }
    } catch (error) {
      console.error('Failed to delete user:', error);
    }
  };

  const startEdit = (user: User) => {
    setEditingUser(user);
    setFormData({ username: user.username, password: '', role: user.role });
  };

  const handleResetData = async () => {
    const confirmation = window.prompt(
      'This will DELETE ALL tournament data, players, matches, and ace pot records. Type "RESET" to confirm:'
    );
    
    if (confirmation !== 'RESET') return;

    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/reset-data`, {
        method: 'DELETE',
        credentials: 'include'
      });
      
      if (response.ok) {
        alert('All data has been reset successfully');
      } else {
        const error = await response.json();
        alert(error.error);
      }
    } catch (error) {
      console.error('Failed to reset data:', error);
    }
  };

  return (
    <div className="admin-container">
      <div className="admin-tabs">
        <button 
          className={activeAdminTab === 'users' ? 'active' : ''}
          onClick={() => setActiveAdminTab('users')}
        >
          User Management
        </button>
        {(currentUser.role === 'Admin' || currentUser.role === 'Director') && (
          <button 
            className={activeAdminTab === 'tournaments' ? 'active' : ''}
            onClick={() => setActiveAdminTab('tournaments')}
          >
            Tournament Edit
          </button>
        )}
        {(currentUser.role === 'Admin' || currentUser.role === 'Director') && (
          <button
            className={activeAdminTab === 'payout' ? 'active' : ''}
            onClick={() => setActiveAdminTab('payout')}
          >
            Season Management
          </button>
        )}
        {currentUser.role === 'Admin' && (
          <button 
            className={activeAdminTab === 'audit' ? 'active' : ''}
            onClick={() => setActiveAdminTab('audit')}
          >
            Tournament Audit
          </button>
        )}
      </div>

      {activeAdminTab === 'users' && (
        <div className="users-management">
          <h2>User Management</h2>
          
          {currentUser.role === 'Admin' && (
            <div className="admin-actions">
              <button onClick={() => setShowCreateForm(true)} className="create-button">
                Create New User
              </button>
              <button onClick={handleResetData} className="reset-button">
                Reset All Data
              </button>
            </div>
          )}

          {showCreateForm && (
            <div className="user-form">
              <h3>Create New User</h3>
              <form onSubmit={handleCreateUser}>
                <input
                  type="text"
                  placeholder="Username"
                  value={formData.username}
                  onChange={(e) => setFormData({...formData, username: e.target.value})}
                  required
                />
                <input
                  type="password"
                  placeholder="Password"
                  value={formData.password}
                  onChange={(e) => setFormData({...formData, password: e.target.value})}
                  required
                />
                <select
                  value={formData.role}
                  onChange={(e) => setFormData({...formData, role: e.target.value})}
                >
                  <option value="Director">Director</option>
                  <option value="Admin">Admin</option>
                </select>
                <div className="form-buttons">
                  <button type="submit">Create</button>
                  <button type="button" onClick={() => setShowCreateForm(false)}>Cancel</button>
                </div>
              </form>
            </div>
          )}

          {editingUser && (
            <div className="user-form">
              <h3>Edit User</h3>
              <form onSubmit={handleUpdateUser}>
                <input
                  type="text"
                  placeholder="Username"
                  value={formData.username}
                  onChange={(e) => setFormData({...formData, username: e.target.value})}
                  required
                />
                <input
                  type="password"
                  placeholder="New Password (leave blank to keep current)"
                  value={formData.password}
                  onChange={(e) => setFormData({...formData, password: e.target.value})}
                />
                {currentUser.role === 'Admin' && (
                  <select
                    value={formData.role}
                    onChange={(e) => setFormData({...formData, role: e.target.value})}
                  >
                    <option value="Director">Director</option>
                    <option value="Admin">Admin</option>
                  </select>
                )}
                <div className="form-buttons">
                  <button type="submit">Update</button>
                  <button type="button" onClick={() => setEditingUser(null)}>Cancel</button>
                </div>
              </form>
            </div>
          )}

          <div className="users-table">
            <table>
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Role</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {currentUser.role === 'Admin' ? users.map(user => (
                  <tr key={user.user_id}>
                    <td>{user.username}</td>
                    <td>{user.role}</td>
                    <td>{new Date(user.created_at).toLocaleDateString()}</td>
                    <td>
                      <button onClick={() => startEdit(user)} className="edit-button">Edit</button>
                      {user.user_id !== currentUser.user_id && (
                        <button onClick={() => handleDeleteUser(user.user_id)} className="delete-button">Delete</button>
                      )}
                    </td>
                  </tr>
                )) : (
                  <tr>
                    <td>{currentUser.username}</td>
                    <td>{currentUser.role}</td>
                    <td>-</td>
                    <td>
                      <button onClick={() => startEdit(currentUser as User)} className="edit-button">Edit Profile</button>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeAdminTab === 'tournaments' && (currentUser.role === 'Admin' || currentUser.role === 'Director') && (
        <div className="tournament-edit-section">
          {selectedTournamentId ? (
            <TournamentEdit 
              tournamentId={selectedTournamentId} 
              onBack={() => setSelectedTournamentId(null)} 
            />
          ) : (
            <div>
              <h2>Select Tournament to Edit</h2>
              <div className="tournament-list">
                {tournaments.length === 0 ? (
                  <p>No in-progress tournaments available for editing.</p>
                ) : (
                  tournaments.map(tournament => (
                    <div 
                      key={tournament.tournament_id} 
                      className="tournament-item"
                      onClick={() => setSelectedTournamentId(tournament.tournament_id)}
                    >
                      <h3>Tournament {tournament.tournament_id}</h3>
                      <p>Date: {new Date(tournament.tournament_date).toLocaleDateString()}</p>
                      <p>Status: {tournament.status}</p>
                      <p>Teams: {tournament.total_teams}</p>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {activeAdminTab === 'audit' && currentUser.role === 'Admin' && (
        <AdminAudit user={currentUser} />
      )}

      {activeAdminTab === 'payout' && (currentUser.role === 'Admin' || currentUser.role === 'Director') && (
        <div className="payout-settings">
          {currentUser.role === 'Admin' && (
            <div className="archive-section">
              <h2>Archive Season</h2>
              <p className="payout-description">
                Archiving ends the current season, resets seasonal stats, and prepares the system for a new season. This action cannot be undone.
              </p>
              <button className="archive-button" onClick={openArchiveWarning}>Archive Season</button>

              {archiveStep === 'warning' && (
                <div className="modal-overlay">
                  <div className="modal">
                    <h3>⚠️ Warning</h3>
                    <p>The Archive action is <strong>destructive and cannot be reversed</strong>. It will reset all seasonal data, prune inactive players, and collapse the ace pot history.</p>
                    <p>Are you sure you want to continue?</p>
                    <div className="modal-buttons">
                      <button onClick={proceedToArchiveForm} disabled={archiveLoading}>Continue</button>
                      <button onClick={cancelArchive}>Cancel</button>
                    </div>
                  </div>
                </div>
              )}

              {archiveStep === 'form' && (
                <div className="modal-overlay">
                  <div className="modal">
                    <h3>Archive Season</h3>
                    {archivePreview && (
                      <table className="payout-preview-table">
                        <tbody>
                          <tr><td>Season Start</td><td>{archivePreview.start_date ?? '—'}</td></tr>
                          <tr><td>Season End</td><td>{archivePreview.end_date ?? '—'}</td></tr>
                          <tr><td>Events</td><td>{archivePreview.event_count}</td></tr>
                          <tr><td>Unique Participants</td><td>{archivePreview.unique_participants}</td></tr>
                          <tr><td>Total Participations</td><td>{archivePreview.total_participants}</td></tr>
                        </tbody>
                      </table>
                    )}
                    <div className="form-section">
                      <label>Season Name:</label>
                      <input
                        type="text"
                        placeholder="e.g. Spring 2026"
                        value={archiveSeasonName}
                        onChange={(e) => setArchiveSeasonName(e.target.value)}
                      />
                    </div>
                    <div className="modal-buttons">
                      <button onClick={performArchive} disabled={archiveLoading || !archiveSeasonName.trim()}>
                        {archiveLoading ? 'Archiving...' : 'Perform Archive'}
                      </button>
                      <button onClick={cancelArchive} disabled={archiveLoading}>Cancel</button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          <h2>Payout Settings</h2>
          <p className="payout-description">
            These values are used as defaults when creating new tournaments. They can be overridden per-tournament on the creation screen.
          </p>

          <div className="form-section">
            <label>Buy-in per Player ($):</label>
            <input
              type="number"
              min="0"
              step="0.25"
              value={payoutSettings.buy_in_per_player}
              onChange={(e) => setPayoutSettings({ ...payoutSettings, buy_in_per_player: parseFloat(e.target.value) || 0 })}
            />
          </div>

          <div className="form-section">
            <label>Payout Mode:</label>
            <div className="mode-toggle">
              <button
                className={payoutSettings.mode === 'fixed' ? 'active' : ''}
                onClick={() => setPayoutSettings({ ...payoutSettings, mode: 'fixed' })}
              >
                Fixed ($)
              </button>
              <button
                className={payoutSettings.mode === 'percentage' ? 'active' : ''}
                onClick={() => setPayoutSettings({ ...payoutSettings, mode: 'percentage' })}
              >
                Percentage (%)
              </button>
            </div>
          </div>

          <div className="form-section">
            <label>
              2nd Place Payout ({payoutSettings.mode === 'fixed' ? '$' : '%'}):
            </label>
            <input
              type="number"
              min="0"
              step={payoutSettings.mode === 'fixed' ? '1' : '1'}
              max={payoutSettings.mode === 'percentage' ? '100' : undefined}
              value={payoutSettings.second_place_value}
              onChange={(e) => setPayoutSettings({ ...payoutSettings, second_place_value: parseFloat(e.target.value) || 0 })}
            />
          </div>

          <div className="payout-preview">
            <h3>Preview (sample: 12 players)</h3>
            {(() => {
              const pot = payoutSettings.buy_in_per_player * 12;
              let second = payoutSettings.mode === 'fixed'
                ? payoutSettings.second_place_value
                : pot * (payoutSettings.second_place_value / 100);
              let first = pot - second;
              if (first < second) { [first, second] = [second, first]; }
              return (
                <table className="payout-preview-table">
                  <tbody>
                    <tr><td>Total pot</td><td>${pot.toFixed(2)}</td></tr>
                    <tr><td>1st place</td><td>${first.toFixed(2)}</td></tr>
                    <tr><td>2nd place</td><td>${second.toFixed(2)}</td></tr>
                  </tbody>
                </table>
              );
            })()}
          </div>

          <div className="default-actions">
            <button className="save-default-button" onClick={savePayoutDefaults}>
              Save as Default
            </button>
            {isCustomPayout && (
              <button className="reset-default-button" onClick={resetPayoutDefaults}>
                Reset to Original Default
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default Admin;
