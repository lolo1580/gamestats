import { Gamepad2, Radio, Wifi, WifiOff } from 'lucide-react'
import type { AgentInfo, GameSession, Summary } from '../types'
import { formatDuration, formatSessionTime } from '../format'
import { useI18n } from '../i18n'
import { Cover } from './Cover'

interface LiveCardProps {
  summary: Summary
  sessions: GameSession[]
  agents: AgentInfo[]
}

export function LiveCard({ summary, sessions, agents }: LiveCardProps) {
  const { t, lang } = useI18n()
  const live = sessions.find((session) => session.is_live)
  const onlineAgents = agents.filter((agent) => agent.online)
  const primaryAgent = onlineAgents[0]

  return (
    <section className="panel live-panel">
      <header className="card-head">
        <div>
          <h2>{t('live.title')}</h2>
          <p>{t('live.subtitle')}</p>
        </div>
        <span className={`live-status${live ? ' is-live' : ''}`}>
          <span className="live-status__dot" />
          {live ? t('live.inGame') : t('live.idle')}
        </span>
      </header>

      {live ? (
        <div className="live-session">
          <Cover
            src={live.cover_url}
            name={live.game_name}
            className="live-session__cover"
            eager
          />
          <div className="live-session__body">
            <span className="live-session__label">
              <Radio size={12} strokeWidth={2.2} />
              {t('live.session')}
            </span>
            <h3>{live.game_name}</h3>
            <p>
              {formatDuration(live.duration_seconds, lang)} ·{' '}
              {t('live.since', { time: formatSessionTime(live.started_at, lang) })}
            </p>
          </div>
        </div>
      ) : (
        <div className="live-idle">
          <span className="live-idle__icon">
            <Gamepad2 size={26} strokeWidth={1.7} />
          </span>
          <div>
            <h3>{t('live.noSession')}</h3>
            <p>{t('live.hint')}</p>
          </div>
        </div>
      )}

      <footer className="live-panel__footer">
        <div className="live-meta">
          <span>{t('live.agentPC')}</span>
          <strong>
            {primaryAgent ? (
              primaryAgent.hostname ?? primaryAgent.agent_id
            ) : (
              <span className="text-muted">
                {onlineAgents.length > 0 ? t('live.connected') : t('live.notConnected')}
              </span>
            )}
          </strong>
        </div>
        <div className="live-meta">
          <span>{t('live.sessions7')}</span>
          <strong>{summary.sessions_week}</strong>
        </div>
        <span className={`agent-state${onlineAgents.length > 0 ? ' is-online' : ''}`}>
          {onlineAgents.length > 0 ? <Wifi size={13} /> : <WifiOff size={13} />}
          {onlineAgents.length > 0 ? t('live.online') : t('live.offline')}
        </span>
      </footer>
    </section>
  )
}
