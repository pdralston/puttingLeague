import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config/api';

interface User {
  user_id: number;
  username: string;
  role: string;
  created_at: string;
}

interface AdminProps {
  currentUser: { user_id: number; username: string; role: string };
}

const Admin: React.FC<AdminProps> = ({ currentUser }) => {
  const [users, setUsers] = useState<User[]>([]);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [formData, setFormData] = useState({ username: '', password: '', role: 'Director' });

  useEffect(() => {
    if (currentUser.role === 'Admin') {
      fetchUsers();
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

  const canEditUser = (user: User) => {
    return currentUser.role === 'Admin' || user.user_id === currentUser.user_id;
  };

  return (
    <div className="admin-container">
      <h2>User Management</h2>
      
      {currentUser.role === 'Admin' && (
        <div className="admin-actions">
          <button onClick={() => setShowCreateForm(true)} className="create-button">
            Create New User
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
  );
};

export default Admin;
