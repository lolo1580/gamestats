import { useMemo } from 'react'
import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import type { DailyStats, Summary } from '../types'
import { formatDuration } from '../format'

interface WeekChartProps {
  daily: DailyStats | null
  summary: Summary
}

function dateLabel(date: string): string {
  const parsed = new Date(`${date}T12:00:00`)
  if (Number.isNaN(parsed.getTime())) return date
  return String(parsed.getDate())
}

function dateTitle(date: string): string {
  const parsed = new Date(`${date}T12:00:00`)
  if (Number.isNaN(parsed.getTime())) return date
  return new Intl.DateTimeFormat('fr-FR', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  }).format(parsed)
}

export function WeekChart({ daily, summary }: WeekChartProps) {
  const items = daily?.items ?? []

  const { lastSevenSeconds, previousSevenSeconds, maxSeconds, totalSeconds } = useMemo(() => {
    const lastSeven = items.slice(-7).reduce((sum, item) => sum + item.seconds, 0)
    const previousSeven = items.slice(-14, -7).reduce((sum, item) => sum + item.seconds, 0)
    const max = Math.max(...items.map((item) => item.seconds), 1)
    const total = items.reduce((sum, item) => sum + item.seconds, 0)
    return {
      lastSevenSeconds: lastSeven,
      previousSevenSeconds: previousSeven,
      maxSeconds: max,
      totalSeconds: total,
    }
  }, [items])

  const weekSeconds = items.length > 0 ? lastSevenSeconds : summary.week_seconds
  const delta =
    previousSevenSeconds > 0
      ? Math.round(((lastSevenSeconds - previousSevenSeconds) / previousSevenSeconds) * 100)
      : null
  const DeltaIcon = delta === null ? Minus : delta >= 0 ? ArrowUpRight : ArrowDownRight
  const deltaLabel =
    delta === null
      ? lastSevenSeconds > 0
        ? 'Nouveau'
        : '—'
      : `${delta > 0 ? '+' : ''}${delta} %`

  const average = Math.round(weekSeconds / 7)

  return (
    <section className="panel chart-panel">
      <header className="card-head">
        <div>
          <h2>Activité récente</h2>
          <p>Temps de jeu quotidien sur 14 jours</p>
        </div>
        <div className="chart-headline">
          <strong>{formatDuration(weekSeconds)}</strong>
          <span>7 derniers jours</span>
        </div>
      </header>

      <div
        className="chart"
        role="img"
        aria-label="Temps de jeu des 14 derniers jours"
      >
        <div className="chart__grid" aria-hidden="true">
          <span />
          <span />
          <span />
          <span />
        </div>
        <div className="chart__bars">
          {items.map((item, index) => {
            const height =
              item.seconds > 0 ? Math.max(4, (item.seconds / maxSeconds) * 100) : 2
            const current = index >= items.length - 7
            return (
              <div
                key={item.date}
                className={`chart__col${current ? ' is-current' : ''}`}
                title={`${dateTitle(item.date)} — ${formatDuration(item.seconds)}`}
              >
                <div className="chart__bar-track">
                  <span
                    className={`chart__bar${item.seconds === 0 ? ' is-empty' : ''}`}
                    style={{ height: `${height}%` }}
                  />
                </div>
                <span className="chart__day">{dateLabel(item.date)}</span>
              </div>
            )
          })}
        </div>
      </div>

      <footer className="chart__footer">
        <div className="chart-stat">
          <span>Moyenne / jour</span>
          <strong>{formatDuration(average)}</strong>
        </div>
        <div className="chart-stat">
          <span>Total 14 jours</span>
          <strong>{formatDuration(totalSeconds)}</strong>
        </div>
        <div className="chart-stat">
          <span>Évolution</span>
          <strong className={`chart-delta${delta !== null && delta < 0 ? ' is-negative' : ''}`}>
            <DeltaIcon size={13} strokeWidth={2.2} />
            {deltaLabel}
          </strong>
        </div>
      </footer>
    </section>
  )
}
