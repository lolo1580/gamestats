import { useMemo, useState } from 'react'
import { History, Radio, Search } from 'lucide-react'
import type { GameSession } from '../types'
import { formatDayLabel, formatDuration, formatSessionTime, localDateKey } from '../format'
import { useI18n } from '../i18n'
import { Cover } from './Cover'

interface SessionsPageProps {
  sessions: GameSession[]
  loading: boolean
}

type SourceFilter = 'all' | 'agent' | 'steam'

export function SessionsPage({ sessions, loading }: SessionsPageProps) {
  const { t, lang } = useI18n()
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
    const term = search.trim().toLocaleLowerCase(lang === 'fr' ? 'fr' : 'en')
    return sessions.filter((session) => {
      if (filter !== 'all' && session.source !== filter) return false
      if (term && !session.game_name.toLocaleLowerCase(lang === 'fr' ? 'fr' : 'en').includes(term)) {
        return false
      }
      return true
    })
  }, [sessions, filter, search, lang])

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

  const filterOptions: { value: SourceFilter; label: string }[] = [
    { value: 'all', label: t('sessions.filtersAll') },
    { value: 'agent', label: t('sessions.filtersAgent') },
    { value: 'steam', label: t('sessions.filtersSteam') },
  ]

  return (
    <div className="page-stack">
      <section className="stats-strip" aria-label={t('sessions.loaded')}>
        <div className="stats-strip__item">
          <span>{t('sessions.loaded')}</span>
          <strong>{sessions.length}</strong>
          <small>{t('sessions.max100')}</small>
        </div>
        <div className="stats-strip__item">
          <span>{t('sessions.totalTime')}</span>
          <strong>{formatDuration(totalSeconds, lang)}</strong>
          <small>{t('sessions.displayedHint')}</small>
        </div>
        <div className="stats-strip__item">
          <span>{t('sessions.live')}</span>
          <strong className="inline-live">
            {liveCount > 0 && <span className="live-dot" />}
            {liveCount > 0
              ? t('status.gamesInProgress', { count: liveCount })
              : t('sessions.none')}
          </strong>
          <small>{t('sessions.pcSteam', { pc: counts.agent, steam: counts.steam })}</small>
        </div>
      </section>

      <section className="panel sessions-panel">
        <div className="toolbar-row">
          <div className="segmented" role="group" aria-label={t('sessions.filtersAll')}>
            {filterOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                className={`segmented__button${filter === option.value ? ' is-active' : ''}`}
                onClick={() => setFilter(option.value)}
              >
                {option.label}
                <span>{counts[option.value]}</span>
              </button>
            ))}
          </div>

          <label className="search-field">
            <Search size={15} strokeWidth={2} />
            <input
              type="search"
              placeholder={t('sessions.search')}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              aria-label={t('sessions.search')}
            />
          </label>
        </div>

        {loading ? (
          <div className="skeleton-list" aria-label={t('page.loading')}>
            {Array.from({ length: 6 }, (_, index) => (
              <span key={index} className="skeleton-row" />
            ))}
          </div>
        ) : groups.length === 0 ? (
          <div className="empty-state">
            <span className="empty-state__icon">
              <History size={26} strokeWidth={1.7} />
            </span>
            <strong>{t('sessions.emptyTitle')}</strong>
            <p>
              {sessions.length === 0
                ? t('sessions.emptyText')
                : t('sessions.noResultsText')}
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
                    <h3>{formatDayLabel(dateKey, lang)}</h3>
                    <span>{formatDuration(daySeconds, lang)}</span>
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
                            <span>
                              {session.is_live
                                ? t('status.inProgress')
                                : t('status.finished')}
                            </span>
                          </div>
                        </div>
                        <span className="history-time">
                          {formatSessionTime(session.started_at, lang)}
                        </span>
                        <span className={`source-badge source-badge--${session.source}`}>
                          {session.source === 'steam' ? t('source.steam') : t('source.pc')}
                        </span>
                        <span className="history-duration">
                          {formatDuration(session.duration_seconds, lang)}
                        </span>
                        <span className={`history-status${session.is_live ? ' is-live' : ''}`}>
                          {session.is_live ? (
                            <>
                              <Radio size={12} strokeWidth={2} />
                              {t('status.inProgress')}
                            </>
                          ) : (
                            t('sessions.endedAt', {
                              time: formatSessionTime(
                                session.ended_at ?? session.started_at,
                                lang,
                              ),
                            })
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
