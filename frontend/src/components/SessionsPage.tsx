import { useMemo, useState } from 'react'
import { History, Radio, Search } from 'lucide-react'
import type { GameSession } from '../types'
import {
  formatDayLabel,
  formatDuration,
  formatSessionTime,
  localDateKey,
  pluralize,
} from '../format'
import { Cover } from './Cover'

interface SessionsPageProps {
  sessions: GameSession[]
  loading: boolean
}

type SourceFilter = 'all' | 'agent' | 'steam'

export function SessionsPage({ sessions, loading }: SessionsPageProps) {
  const [filter, setFilter] = useState<SourceFilter>('all')
  const [search, setSearch] = useState('')

  const counts = useMemo(
    () => ({
      all: sessions.length,
      agent: sessions.filter((session) => session.source === 'agent').length,
      steam: sessions.filter((session) => session.source === 'steam').length,
    }),
    [sessions],
  )

  const totalSeconds = useMemo(
    () => sessions.reduce((sum, session) => sum + session.duration_seconds, 0),
    [sessions],
  )
  const liveCount = sessions.filter((session) => session.is_live).length

  const filtered = useMemo(() => {
    const term = search.trim().toLocaleLowerCase('fr')
    return sessions.filter((session) => {
      if (filter !== 'all' && session.source !== filter) return false
      if (term && !session.game_name.toLocaleLowerCase('fr').includes(term)) return false
      return true
    })
  }, [sessions, filter, search])

  const groups = useMemo(() => {
    const map = new Map<string, GameSession[]>()
    for (const session of filtered) {
      const key = localDateKey(new Date(session.started_at))
      const bucket = map.get(key)
      if (bucket) bucket.push(session)
      else map.set(key, [session])
    }
    return Array.from(map.entries())
  }, [filtered])

  return (
    <div className="page-stack">
      <section className="stats-strip" aria-label="Résumé des sessions">
        <div className="stats-strip__item">
          <span>Sessions chargées</span>
          <strong>{sessions.length}</strong>
          <small>100 dernières maximum</small>
        </div>
        <div className="stats-strip__item">
          <span>Temps cumulé</span>
          <strong>{formatDuration(totalSeconds)}</strong>
          <small>sur les sessions affichées</small>
        </div>
        <div className="stats-strip__item">
          <span>En direct</span>
          <strong className="inline-live">
            {liveCount > 0 && <span className="live-dot" />}
            {liveCount > 0 ? pluralize(liveCount, 'jeu', 'jeux') : 'Aucun'}
          </strong>
          <small>
            {counts.agent} PC · {counts.steam} Steam
          </small>
        </div>
      </section>

      <section className="panel sessions-panel">
        <div className="toolbar-row">
          <div className="segmented" role="group" aria-label="Filtrer par source">
            {(
              [
                ['all', 'Toutes'],
                ['agent', 'Agent PC'],
                ['steam', 'Steam'],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                className={`segmented__button${filter === value ? ' is-active' : ''}`}
                onClick={() => setFilter(value)}
              >
                {label}
                <span>{counts[value]}</span>
              </button>
            ))}
          </div>

          <label className="search-field">
            <Search size={15} strokeWidth={2} />
            <input
              type="search"
              placeholder="Rechercher un jeu…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              aria-label="Rechercher dans les sessions"
            />
          </label>
        </div>

        {loading ? (
          <div className="skeleton-list" aria-label="Chargement des sessions">
            {Array.from({ length: 6 }, (_, index) => (
              <span key={index} className="skeleton-row" />
            ))}
          </div>
        ) : groups.length === 0 ? (
          <div className="empty-state">
            <span className="empty-state__icon">
              <History size={26} strokeWidth={1.7} />
            </span>
            <strong>Aucune session trouvée</strong>
            <p>
              {sessions.length === 0
                ? "L'historique se remplira dès qu'un jeu sera détecté."
                : 'Essaie un autre filtre ou un autre titre.'}
            </p>
          </div>
        ) : (
          <div className="day-groups">
            {groups.map(([dateKey, daySessions]) => {
              const daySeconds = daySessions.reduce(
                (sum, session) => sum + session.duration_seconds,
                0,
              )
              return (
                <section key={dateKey} className="day-group">
                  <header className="day-group__head">
                    <h3>{formatDayLabel(dateKey)}</h3>
                    <span>{formatDuration(daySeconds)}</span>
                  </header>

                  <div className="history-table">
                    {daySessions.map((session) => (
                      <article
                        key={session.id}
                        className={`history-row${session.is_live ? ' is-live' : ''}`}
                      >
                        <div className="history-game">
                          <Cover
                            src={session.cover_url}
                            name={session.game_name}
                            className="history-game__cover"
                          />
                          <div>
                            <h4 title={session.game_name}>{session.game_name}</h4>
                            <span>{session.is_live ? 'En cours' : 'Partie terminée'}</span>
                          </div>
                        </div>
                        <span className="history-time">
                          {formatSessionTime(session.started_at)}
                        </span>
                        <span className={`source-badge source-badge--${session.source}`}>
                          {session.source === 'steam' ? 'Steam' : 'PC'}
                        </span>
                        <span className="history-duration">
                          {formatDuration(session.duration_seconds)}
                        </span>
                        <span className={`history-status${session.is_live ? ' is-live' : ''}`}>
                          {session.is_live ? (
                            <>
                              <Radio size={12} strokeWidth={2} />
                              En cours
                            </>
                          ) : (
                            'Terminée'
                          )}
                        </span>
                      </article>
                    ))}
                  </div>
                </section>
              )
            })}
          </div>
        )}
      </section>
    </div>
  )
}
