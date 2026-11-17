import { Activity, CalendarDays, Clock3, LibraryBig } from 'lucide-react'
import type { DailyStats, Summary } from '../types'
import { formatDuration } from '../format'
import { useI18n } from '../i18n'

interface StatCardsProps {
  summary: Summary
  daily: DailyStats | null
}

export function StatCards({ summary, daily }: StatCardsProps) {
  const { t, lang } = useI18n()
  const items = daily?.items ?? []
  const lastSeven = items.slice(-7).reduce((sum, item) => sum + item.seconds, 0)
  const previousSeven = items.slice(-14, -7).reduce((sum, item) => sum + item.seconds, 0)
  const delta =
    previousSeven > 0 ? Math.round(((lastSeven - previousSeven) / previousSeven) * 100) : null
  const weekSeconds = items.length > 0 ? lastSeven : summary.week_seconds

  const evolution =
    delta === null
      ? lastSeven > 0
        ? t('kpi.newActivity')
        : t('kpi.noData')
      : t('kpi.evolution', { delta: `${delta > 0 ? '+' : ''}${delta}` })

  return (
    <section className="kpi-grid" aria-label={t('page.overview.title')}>
      <article className="kpi-card">
        <div className="kpi-card__head">
          <span className="kpi-card__label">{t('kpi.today')}</span>
          <span className="kpi-card__icon">
            <Clock3 size={17} strokeWidth={2} />
          </span>
        </div>
        <strong className="kpi-card__value">
          {formatDuration(summary.today_seconds, lang)}
        </strong>
        <span className="kpi-card__detail">
          {t('kpi.sessionsWeek', { count: summary.sessions_week })}
        </span>
      </article>

      <article className="kpi-card">
        <div className="kpi-card__head">
          <span className="kpi-card__label">{t('kpi.week')}</span>
          <span className="kpi-card__icon">
            <CalendarDays size={17} strokeWidth={2} />
          </span>
        </div>
        <strong className="kpi-card__value">{formatDuration(weekSeconds, lang)}</strong>
        <span className={`kpi-card__detail${delta !== null && delta < 0 ? ' is-negative' : ''}`}>
          {evolution}
        </span>
      </article>

      <article className="kpi-card">
        <div className="kpi-card__head">
          <span className="kpi-card__label">{t('kpi.total')}</span>
          <span className="kpi-card__icon">
            <Activity size={17} strokeWidth={2} />
          </span>
        </div>
        <strong className="kpi-card__value">
          {formatDuration(summary.total_seconds, lang)}
        </strong>
        <span className="kpi-card__detail">{t('kpi.agentSteam')}</span>
      </article>

      <article className="kpi-card">
        <div className="kpi-card__head">
          <span className="kpi-card__label">{t('kpi.library')}</span>
          <span className="kpi-card__icon">
            <LibraryBig size={17} strokeWidth={2} />
          </span>
        </div>
        <strong className="kpi-card__value">
          {summary.library_count} {t('library.games')}
        </strong>
        <span className="kpi-card__detail">
          {t('kpi.activeGames', { count: summary.distinct_games_week })}
        </span>
      </article>
    </section>
  )
}
