import React, { useState } from 'react';
import './App.css';
import './components/Bracket.css';
import './components/PlayerManager.css';
import './components/Leaderboard.css';
import './components/TournamentDirectory.css';

import './components/AcePotTracker.css';
import './components/TournamentCreation.css';
import UnifiedTournamentView from './components/UnifiedTournamentView';
import TournamentDirectory from './components/TournamentDirectory';

import TournamentCreation from './components/TournamentCreation';
import PlayerManager from './components/PlayerManager';
import Leaderboard from './components/Leaderboard';
import AcePotTracker from './components/AcePotTracker';

function App() {
  const [activeTab, setActiveTab] = useState<'players' | 'leaderboard' | 'tournaments' | 'ace-pot'>('players');
  const [selectedTournament, setSelectedTournament] = useState<number | null>(null);
  const [tournamentMode, setTournamentMode] = useState<'view' | 'manage' | 'create'>('view');

  const handleTournamentSelect = (tournamentId: number) => {
    setSelectedTournament(tournamentId);
    setTournamentMode('view');
  };

  const handleTournamentManage = (tournamentId: number) => {
    setSelectedTournament(tournamentId);
    setTournamentMode('manage');
  };

  const handleCreateTournament = () => {
    setSelectedTournament(null);
    setTournamentMode('create');
  };

  const handleBackToDirectory = () => {
    setSelectedTournament(null);
    setTournamentMode('view');
  };

  const handleTournamentCreated = () => {
    setTournamentMode('view');
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>DG Putt</h1>
        <nav>
          <button 
            className={activeTab === 'players' ? 'active' : ''}
            onClick={() => setActiveTab('players')}
          >
            Players
          </button>
          <button 
            className={activeTab === 'leaderboard' ? 'active' : ''}
            onClick={() => setActiveTab('leaderboard')}
          >
            Leaderboard
          </button>
          <button 
            className={activeTab === 'tournaments' ? 'active' : ''}
            onClick={() => {
              setActiveTab('tournaments');
              setSelectedTournament(null);
              setTournamentMode('view');
            }}
          >
            Tournaments
          </button>
          <button 
            className={activeTab === 'ace-pot' ? 'active' : ''}
            onClick={() => setActiveTab('ace-pot')}
          >
            Ace Pot
          </button>
        </nav>
      </header>
      <main>
        {activeTab === 'players' && <PlayerManager />}
        {activeTab === 'leaderboard' && <Leaderboard />}
        {activeTab === 'ace-pot' && <AcePotTracker />}
        {activeTab === 'tournaments' && !selectedTournament && tournamentMode !== 'create' && (
          <TournamentDirectory 
            onTournamentSelect={handleTournamentSelect}
            onTournamentManage={handleTournamentManage}
            onCreateTournament={handleCreateTournament}
          />
        )}
        {activeTab === 'tournaments' && tournamentMode === 'create' && (
          <TournamentCreation
            onBack={handleBackToDirectory}
            onTournamentCreated={handleTournamentCreated}
          />
        )}
        {activeTab === 'tournaments' && selectedTournament && tournamentMode === 'view' && (
          <UnifiedTournamentView 
            tournamentId={selectedTournament} 
            onBack={handleBackToDirectory}
            showManagementActions={false}
          />
        )}
        {activeTab === 'tournaments' && selectedTournament && tournamentMode === 'manage' && (
          <UnifiedTournamentView 
            tournamentId={selectedTournament} 
            onBack={handleBackToDirectory}
            showManagementActions={true}
          />
        )}
      </main>
    </div>
  );
}

export default App;
