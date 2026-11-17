import { ArrowRight, History } from 'lucide-react'
import type { GameSession } from '../types'
import { formatDuration, formatSessionStart } from '../format'
import { useI18n } from '../i18n'
import { Cover } from './Cover'

interface RecentSessionsProps {
  sessions: GameSession[]
  onViewAll: () => void
}

export function RecentSessions({ sessions, onViewAll }: RecentSessionsProps) {
  const { t, lang } = useI18n()

  return (
    <section className="panel table-panel">
      <header className="card-head">
        <div>
          <h2>{t('recent.title')}</h2>
          <p>{t('recent.subtitle')}</p>
        </div>
        <button type="button" className="text-link" onClick={onViewAll}>
          {t('recent.viewAll')}
          <ArrowRight size={13} strokeWidth={2.2} />
        </button>
      </header>

      {sessions.length === 0 ? (
        <div className="empty-state empty-state--compact">
          <span className="empty-state__icon">
            <History size={24} strokeWidth={1.7} />
          </span>
          <strong>{t('recent.emptyTitle')}</strong>
          <p>{t('recent.emptyText')}</p>
        </div>
      ) : (
        <div className="data-table">
          <div className="data-table__head" aria-hidden="true">
            <span>{t('table.game')}</span>
            <span>{t('table.start')}</span>
            <span>{t('table.duration')}</span>
            <span>{t('table.source')}</span>
            <span>{t('table.status')}</span>
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
                  <span>
                    {session.source === 'steam' ? t('source.steam') : t('agent.pc')}
                  </span>
                </div>
              </div>
              <span className="table-date">
                {formatSessionStart(session.started_at, lang)}
              </span>
              <span className="table-duration">
                {formatDuration(session.duration_seconds, lang)}
              </span>
              <span>
                <span className={`source-badge source-badge--${session.source}`}>
                  {session.source === 'steam' ? t('source.steam') : t('source.pc')}
                </span>
              </span>
              <span className={`table-status${session.is_live ? ' is-live' : ''}`}>
                <span className="table-status__dot" />
                {session.is_live ? t('status.inProgress') : t('status.finished')}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
