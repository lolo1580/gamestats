import { Fragment, useMemo } from 'react'
import { Zap } from 'lucide-react'
import type { HeatmapData } from '../types'
import { formatCompactDuration, formatDuration, localeFor } from '../format'
import { useI18n } from '../i18n'

interface HeatmapProps {
  data: HeatmapData
}

const HOURS = Array.from({ length: 24 }, (_, hour) => hour)

function weekdayLabels(lang: 'fr' | 'en', style: 'short' | 'long'): string[] {
  const formatter = new Intl.DateTimeFormat(localeFor(lang), { weekday: style })
  return Array.from({ length: 7 }, (_, index) =>
    formatter.format(new Date(Date.UTC(2024, 0, 1 + index))),
  )
}

export function Heatmap({ data }: HeatmapProps) {
  const { t, lang } = useI18n()
  const daysShort = useMemo(() => weekdayLabels(lang, 'short'), [lang])
  const daysLong = useMemo(() => weekdayLabels(lang, 'long'), [lang])

  const { matrix, rowTotals, total, peak } = useMemo(() => {
    const grid = Array.from({ length: 7 }, () => Array<number>(24).fill(0))
    for (const cell of data.cells) {
      if (cell.weekday >= 0 && cell.weekday < 7 && cell.hour >= 0 && cell.hour < 24) {
        grid[cell.weekday][cell.hour] = cell.seconds
      }
    }

    let best = { weekday: -1, hour: -1, seconds: 0 }
    for (let weekday = 0; weekday < 7; weekday += 1) {
      for (let hour = 0; hour < 24; hour += 1) {
        if (grid[weekday][hour] > best.seconds) {
          best = { weekday, hour, seconds: grid[weekday][hour] }
        }
      }
    }

    return {
      matrix: grid,
      rowTotals: grid.map((row) => row.reduce((sum, value) => sum + value, 0)),
      total: grid.flat().reduce((sum, value) => sum + value, 0),
      peak: best,
    }
  }, [data.cells])

  const max = Math.max(data.max_seconds, 1)
  const peakLabel =
    peak.seconds > 0
      ? `${daysShort[peak.weekday]} ${String(peak.hour).padStart(2, '0')}h`
      : t('heatmap.noPeak')

  return (
    <section className="panel heatmap-panel">
      <header className="card-head">
        <div>
          <h2>{t('heatmap.title')}</h2>
          <p>{t('heatmap.subtitle', { duration: formatDuration(total, lang) })}</p>
        </div>
        <span className="badge badge--accent">
          <Zap size={13} strokeWidth={2.2} />
          {t('heatmap.peak', { label: peakLabel })}
        </span>
      </header>

      <div className="heatmap-scroll">
        <div className="heatmap" role="img" aria-label={t('heatmap.aria')}>
          <div className="heatmap__corner" />
          {HOURS.map((hour) => (
            <div key={hour} className="heatmap__hour">
              {hour % 3 === 0 ? `${hour}h` : ''}
            </div>
          ))}
          <div className="heatmap__total-head">Total</div>

          {matrix.map((row, weekday) => (
            <Fragment key={weekday}>
              <div className="heatmap__day">{daysShort[weekday]}</div>
              {row.map((seconds, hour) => {
                const intensity = seconds > 0 ? Math.sqrt(seconds / max) : 0
                const background =
                  seconds > 0
                    ? `rgba(76, 141, 255, ${0.12 + intensity * 0.88})`
                    : undefined

                return (
                  <div
                    key={`${weekday}-${hour}`}
                    className={`heat-cell${seconds > 0 ? ' is-filled' : ''}`}
                    style={{ background }}
                    title={`${daysLong[weekday]} ${String(hour).padStart(2, '0')}:00 — ${
                      seconds > 0 ? formatDuration(seconds, lang) : '—'
                    }`}
                  />
                )
              })}
              <div className="heatmap__row-total">
                {formatCompactDuration(rowTotals[weekday], lang)}
              </div>
            </Fragment>
          ))}
        </div>
      </div>

      <footer className="heatmap__footer">
        <div className="heatmap__legend">
          <span>{t('heatmap.less')}</span>
          <div className="heatmap__scale" aria-hidden="true">
            {[0.12, 0.28, 0.46, 0.64, 0.82, 1].map((opacity) => (
              <span key={opacity} style={{ background: `rgba(76, 141, 255, ${opacity})` }} />
            ))}
          </div>
          <span>{t('heatmap.more')}</span>
        </div>
        <span>{t('heatmap.note')}</span>
      </footer>
    </section>
  )
}
