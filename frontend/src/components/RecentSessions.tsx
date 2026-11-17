import { ArrowRight, History } from 'lucide-react'
import type { GameSession } from '../types'
import { formatDuration, formatSessionStart } from '../format'
import { Cover } from './Cover'

interface RecentSessionsProps {
  sessions: GameSession[]
  onViewAll: () => void
}

export function RecentSessions({ sessions, onViewAll }: RecentSessionsProps) {
  return (
    <section className="panel table-panel">
      <header className="card-head">
        <div>
          <h2>Sessions récentes</h2>
          <p>Dernières parties détectées</p>
        </div>
        <button type="button" className="text-link" onClick={onViewAll}>
          Tout voir
          <ArrowRight size={13} strokeWidth={2.2} />
        </button>
      </header>

      {sessions.length === 0 ? (
        <div className="empty-state empty-state--compact">
          <span className="empty-state__icon">
            <History size={24} strokeWidth={1.7} />
          </span>
          <strong>Pas encore de session</strong>
          <p>Configure l'agent Windows pour démarrer le suivi en temps réel.</p>
        </div>
      ) : (
        <div className="data-table">
          <div className="data-table__head" aria-hidden="true">
            <span>Jeu</span>
            <span>Début</span>
            <span>Durée</span>
            <span>Source</span>
            <span>Statut</span>
          </div>

          {sessions.map((session) => (
            <div
              key={session.id}
              className={`data-table__row${session.is_live ? ' is-live' : ''}`}
            >
              <div className="table-game">
                <Cover
                  src={session.cover_url}
                  name={session.game_name}
                  className="table-game__cover"
                />
                <div className="table-game__copy">
                  <h3 title={session.game_name}>{session.game_name}</h3>
                  <span>{session.source === 'steam' ? 'Steam' : 'Agent PC'}</span>
                </div>
              </div>
              <span className="table-date">{formatSessionStart(session.started_at)}</span>
              <span className="table-duration">{formatDuration(session.duration_seconds)}</span>
              <span>
                <span className={`source-badge source-badge--${session.source}`}>
                  {session.source === 'steam' ? 'Steam' : 'PC'}
                </span>
              </span>
              <span className={`table-status${session.is_live ? ' is-live' : ''}`}>
                <span className="table-status__dot" />
                {session.is_live ? 'En cours' : 'Terminée'}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
