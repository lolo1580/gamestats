import { Gamepad2, Radio, Wifi, WifiOff } from 'lucide-react'
import type { AgentInfo, GameSession, Summary } from '../types'
import { formatDuration, formatSessionTime } from '../format'
import { Cover } from './Cover'

interface LiveCardProps {
  summary: Summary
  sessions: GameSession[]
  agents: AgentInfo[]
}

export function LiveCard({ summary, sessions, agents }: LiveCardProps) {
  const live = sessions.find((session) => session.is_live)
  const onlineAgents = agents.filter((agent) => agent.online)
  const primaryAgent = onlineAgents[0]

  return (
    <section className="panel live-panel">
      <header className="card-head">
        <div>
          <h2>En ce moment</h2>
          <p>État du suivi en direct</p>
        </div>
        <span className={`live-status${live ? ' is-live' : ''}`}>
          <span className="live-status__dot" />
          {live ? 'En jeu' : 'Au repos'}
        </span>
      </header>

      {live ? (
        <div className="live-session">
          <Cover src={live.cover_url} name={live.game_name} className="live-session__cover" eager />
          <div className="live-session__body">
            <span className="live-session__label">
              <Radio size={12} strokeWidth={2.2} />
              Session en cours
            </span>
            <h3>{live.game_name}</h3>
            <p>
              {formatDuration(live.duration_seconds)} · depuis{' '}
              {formatSessionTime(live.started_at)}
            </p>
          </div>
        </div>
      ) : (
        <div className="live-idle">
          <span className="live-idle__icon">
            <Gamepad2 size={26} strokeWidth={1.7} />
          </span>
          <div>
            <h3>Aucune session active</h3>
            <p>Lance un jeu suivi par l'agent pour démarrer le suivi.</p>
          </div>
        </div>
      )}

      <footer className="live-panel__footer">
        <div className="live-meta">
          <span>Agent PC</span>
          <strong>
            {primaryAgent ? (
              primaryAgent.hostname ?? primaryAgent.agent_id
            ) : (
              <span className="text-muted">
                {onlineAgents.length > 0 ? 'Connecté' : 'Non connecté'}
              </span>
            )}
          </strong>
        </div>
        <div className="live-meta">
          <span>Sessions / 7 j</span>
          <strong>{summary.sessions_week}</strong>
        </div>
        <span className={`agent-state${onlineAgents.length > 0 ? ' is-online' : ''}`}>
          {onlineAgents.length > 0 ? <Wifi size={13} /> : <WifiOff size={13} />}
          {onlineAgents.length > 0 ? 'En ligne' : 'Hors ligne'}
        </span>
      </footer>
    </section>
  )
}
