import type {
  AgentInfo,
  DailyStats,
  Game,
  GameSession,
  HeatmapData,
  Summary,
  TopGame,
} from './types'

const API_BASE = (import.meta.env.VITE_API_URL ?? '/api').replace(/\/$/, '')

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: 'application/json' },
  })

  if (!response.ok) {
    let detail = `Erreur ${response.status}`
    try {
      const body = (await response.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // Réponse non JSON : on garde le message générique.
    }
    throw new Error(detail)
  }

  return (await response.json()) as T
}

export const api = {
  summary: () => get<Summary>('/stats/summary'),
  heatmap: (days = 365) => get<HeatmapData>(`/stats/heatmap?days=${days}`),
  daily: (days = 14) => get<DailyStats>(`/stats/daily?days=${days}`),
  topGames: (days = 30, limit = 6) =>
    get<TopGame[]>(`/stats/top-games?days=${days}&limit=${limit}`),
  sessions: (limit = 100) => get<GameSession[]>(`/sessions?limit=${limit}`),
  games: (limit = 1000) => get<Game[]>(`/games?limit=${limit}`),
  agents: () => get<AgentInfo[]>('/agents'),
}
