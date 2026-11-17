import { ArrowRight, Gamepad2, Trophy } from 'lucide-react'
import type { TopGame } from '../types'
import { formatDuration } from '../format'
import { Cover } from './Cover'

interface TopGamesProps {
  games: TopGame[]
  days: number
  onBrowse: () => void
}

export function TopGames({ games, days, onBrowse }: TopGamesProps) {
  const max = Math.max(games[0]?.tracked_seconds ?? 0, 1)

  return (
    <section className="panel top-panel">
      <header className="card-head">
        <div>
          <h2>Top jeux</h2>
          <p>Temps suivi sur {days} jours</p>
        </div>
        <button type="button" className="text-link" onClick={onBrowse}>
          Bibliothèque
          <ArrowRight size={13} strokeWidth={2.2} />
        </button>
      </header>

      {games.length === 0 ? (
        <div className="empty-state empty-state--compact">
          <span className="empty-state__icon">
            <Gamepad2 size={24} strokeWidth={1.7} />
          </span>
          <strong>Aucune session sur la période</strong>
          <p>Les jeux apparaîtront ici après le lancement de l'agent.</p>
        </div>
      ) : (
        <ol className="top-list">
          {games.map((game, index) => (
            <li key={game.id} className="top-item">
              <span className="top-item__rank">{String(index + 1).padStart(2, '0')}</span>
              <Cover src={game.cover_url} name={game.name} className="top-item__cover" />
              <div className="top-item__main">
                <div className="top-item__line">
                  <h3 title={game.name}>{game.name}</h3>
                  <span>{formatDuration(game.tracked_seconds)}</span>
                </div>
                <div className="top-item__meta">
                  <span>{game.genres.slice(0, 2).join(' · ') || 'Jeu PC'}</span>
                  {game.achievements_total > 0 && (
                    <span className="top-item__achievements">
                      <Trophy size={11} strokeWidth={2.2} />
                      {game.achievements_unlocked}/{game.achievements_total}
                    </span>
                  )}
                </div>
                <div className="top-item__bar" aria-hidden="true">
                  <span style={{ width: `${Math.max(3, (game.tracked_seconds / max) * 100)}%` }} />
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
