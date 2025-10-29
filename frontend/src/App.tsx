import React, { useState } from 'react';
import './App.css';
import './components/Bracket.css';
import './components/PlayerManager.css';
import './components/Leaderboard.css';
import './components/TournamentDirectory.css';
import './components/AcePotTracker.css';
import TournamentBracket from './components/TournamentBracket';
import TournamentDirectory from './components/TournamentDirectory';
import PlayerManager from './components/PlayerManager';
import Leaderboard from './components/Leaderboard';
import AcePotTracker from './components/AcePotTracker';

function App() {
  const [activeTab, setActiveTab] = useState<'players' | 'leaderboard' | 'tournaments' | 'ace-pot'>('players');
  const [selectedTournament, setSelectedTournament] = useState<number | null>(null);

  const handleTournamentSelect = (tournamentId: number) => {
    setSelectedTournament(tournamentId);
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
          <TournamentDirectory onTournamentSelect={handleTournamentSelect} />
        )}
        {activeTab === 'tournaments' && selectedTournament && (
          <div>
            <div className="back-button-container">
              <button className="back-button" onClick={handleBackToDirectory}>
                ← Back to Tournaments
              </button>
            </div>
            <TournamentBracket tournamentId={selectedTournament} />
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
