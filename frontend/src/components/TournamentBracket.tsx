import React, { useEffect, useState } from 'react';
import Bracket from './Bracket';
import { Tournament } from '../types/tournament';

interface TournamentBracketProps {
  tournamentId: number;
}

const TournamentBracket: React.FC<TournamentBracketProps> = ({ tournamentId }) => {
  const [tournament, setTournament] = useState<Tournament | null>(null);
  const [players, setPlayers] = useState<any[]>([]);

  useEffect(() => {
    Promise.all([
      fetch(`http://localhost:5000/api/tournaments/${tournamentId}/matches`).then(res => res.json()),
      fetch(`http://localhost:5000/api/tournaments/${tournamentId}/teams`).then(res => res.json())
    ]).then(([matches, teams]) => {
      setTournament({ id: tournamentId, name: `Tournament ${tournamentId}`, teams, matches });
    });
  }, [tournamentId]);

  const handleScoreMatch = async (matchId: number, team1Score: number, team2Score: number) => {
    console.log('Scoring match:', matchId, 'Scores:', team1Score, team2Score);
    try {
      const response = await fetch(`http://localhost:5000/api/tournaments/${tournamentId}/matches/${matchId}/score`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ team1_score: team1Score, team2_score: team2Score })
      });
      
      const result = await response.json();
      console.log('Score response:', result);
      
      if (response.ok) {
        // Refresh tournament data
        const [matches, teams] = await Promise.all([
          fetch(`http://localhost:5000/api/tournaments/${tournamentId}/matches`).then(res => res.json()),
          fetch(`http://localhost:5000/api/tournaments/${tournamentId}/teams`).then(res => res.json())
        ]);
        setTournament({ id: tournamentId, name: `Tournament ${tournamentId}`, teams, matches });
      } else {
        console.error('Failed to score match:', result);
      }
    } catch (error) {
      console.error('Failed to score match:', error);
    }
  };

  const handleStartMatch = async (matchId: number) => {
    try {
      const response = await fetch(`http://localhost:5000/api/tournaments/${tournamentId}/matches/${matchId}/start`, {
        method: 'POST'
      });
      if (response.ok) {
        // Refresh tournament data
        const [matches, teams] = await Promise.all([
          fetch(`http://localhost:5000/api/tournaments/${tournamentId}/matches`).then(res => res.json()),
          fetch(`http://localhost:5000/api/tournaments/${tournamentId}/teams`).then(res => res.json())
        ]);
        setTournament({ id: tournamentId, name: `Tournament ${tournamentId}`, teams, matches });
      }
    } catch (error) {
      console.error('Failed to start match:', error);
    }
  };

  if (!tournament) return <div>Loading...</div>;

  const winnersMatches = tournament.matches.filter(m => m.round_type === 'Winners');
  const losersMatches = tournament.matches.filter(m => m.round_type === 'Losers');

  return (
    <div className="tournament-bracket">
      <h2>{tournament.name}</h2>
      <p>Total matches: {tournament.matches.length}</p>
      <div className="brackets">
        <Bracket matches={winnersMatches} allMatches={tournament.matches} teams={tournament.teams} players={players} title="Winners Bracket" onStartMatch={handleStartMatch} onScoreMatch={handleScoreMatch} />
        <Bracket matches={losersMatches} allMatches={tournament.matches} teams={tournament.teams} players={players} title="Losers Bracket" onStartMatch={handleStartMatch} onScoreMatch={handleScoreMatch} />
      </div>
    </div>
  );
};

export default TournamentBracket;
