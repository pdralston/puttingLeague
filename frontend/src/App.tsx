import React, { useState } from 'react';
import './App.css';
import './components/Bracket.css';
import './components/PlayerManager.css';
import './components/Leaderboard.css';
import './components/TournamentDirectory.css';
import './components/TournamentView.css';
import './components/AcePotTracker.css';
import TournamentBracket from './components/TournamentBracket';
import TournamentDirectory from './components/TournamentDirectory';
import TournamentView from './components/TournamentView';
import PlayerManager from './components/PlayerManager';
import Leaderboard from './components/Leaderboard';
import AcePotTracker from './components/AcePotTracker';

function App() {
  const [activeTab, setActiveTab] = useState<'players' | 'leaderboard' | 'tournaments' | 'ace-pot'>('players');
  const [selectedTournament, setSelectedTournament] = useState<number | null>(null);
  const [tournamentMode, setTournamentMode] = useState<'view' | 'manage'>('view');

  const handleTournamentSelect = (tournamentId: number) => {
    setSelectedTournament(tournamentId);
    setTournamentMode('view');
  };

  const handleTournamentManage = (tournamentId: number) => {
    setSelectedTournament(tournamentId);
    setTournamentMode('manage');
  };

  const handleBackToDirectory = () => {
    setSelectedTournament(null);
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
        {activeTab === 'tournaments' && !selectedTournament && (
          <TournamentDirectory 
            onTournamentSelect={handleTournamentSelect}
            onTournamentManage={handleTournamentManage}
          />
        )}
        {activeTab === 'tournaments' && selectedTournament && tournamentMode === 'view' && (
          <TournamentView 
            tournamentId={selectedTournament} 
            onBack={handleBackToDirectory}
          />
        )}
        {activeTab === 'tournaments' && selectedTournament && tournamentMode === 'manage' && (
          <TournamentBracket 
            tournamentId={selectedTournament} 
            onBack={handleBackToDirectory}
          />
        )}
      </main>
    </div>
  );
}

export default App;
