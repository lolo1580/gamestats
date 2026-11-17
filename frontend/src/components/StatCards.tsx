import { Activity, CalendarDays, Clock3, LibraryBig } from 'lucide-react'
import type { DailyStats, Summary } from '../types'
import { formatDuration } from '../format'

interface StatCardsProps {
  summary: Summary
  daily: DailyStats | null
}

export function StatCards({ summary, daily }: StatCardsProps) {
  const items = daily?.items ?? []
  const lastSeven = items.slice(-7).reduce((sum, item) => sum + item.seconds, 0)
  const previousSeven = items.slice(-14, -7).reduce((sum, item) => sum + item.seconds, 0)
  const delta =
    previousSeven > 0 ? Math.round(((lastSeven - previousSeven) / previousSeven) * 100) : null
  const weekSeconds = items.length > 0 ? lastSeven : summary.week_seconds

  const evolution =
    delta === null
      ? lastSeven > 0
        ? 'Nouvelle activité'
        : 'Pas encore de données'
      : `${delta > 0 ? '+' : ''}${delta} % vs 7 jours précédents`

  return (
    <section className="kpi-grid" aria-label="Chiffres clés">
      <article className="kpi-card">
        <div className="kpi-card__head">
          <span className="kpi-card__label">Aujourd'hui</span>
          <span className="kpi-card__icon">
            <Clock3 size={17} strokeWidth={2} />
          </span>
        </div>
        <strong className="kpi-card__value">{formatDuration(summary.today_seconds)}</strong>
        <span className="kpi-card__detail">
          {summary.sessions_week} sessions sur 7 jours
        </span>
      </article>

      <article className="kpi-card">
        <div className="kpi-card__head">
          <span className="kpi-card__label">7 derniers jours</span>
          <span className="kpi-card__icon">
            <CalendarDays size={17} strokeWidth={2} />
          </span>
        </div>
        <strong className="kpi-card__value">{formatDuration(weekSeconds)}</strong>
        <span className={`kpi-card__detail${delta !== null && delta < 0 ? ' is-negative' : ''}`}>
          {evolution}
        </span>
      </article>

      <article className="kpi-card">
        <div className="kpi-card__head">
          <span className="kpi-card__label">Temps total suivi</span>
          <span className="kpi-card__icon">
            <Activity size={17} strokeWidth={2} />
          </span>
        </div>
        <strong className="kpi-card__value">{formatDuration(summary.total_seconds)}</strong>
        <span className="kpi-card__detail">Agent PC + deltas Steam</span>
      </article>

      <article className="kpi-card">
        <div className="kpi-card__head">
          <span className="kpi-card__label">Bibliothèque</span>
          <span className="kpi-card__icon">
            <LibraryBig size={17} strokeWidth={2} />
          </span>
        </div>
        <strong className="kpi-card__value">{summary.library_count} jeux</strong>
        <span className="kpi-card__detail">
          {summary.distinct_games_week} jeux actifs cette semaine
        </span>
      </article>
    </section>
  )
}
