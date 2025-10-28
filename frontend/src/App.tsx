import React from 'react';
import './App.css';
import './components/Bracket.css';
import TournamentBracket from './components/TournamentBracket';

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <h1>DG Putt Tournament Brackets</h1>
      </header>
      <main>
        <TournamentBracket tournamentId={31} />
      </main>
    </div>
  );
}

export default App;
