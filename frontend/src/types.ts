export type Page = 'overview' | 'library' | 'sessions' | 'settings'

export type Theme = 'dark' | 'light'

export type UserRole = 'admin' | 'viewer'

export interface CurrentUser {
  id: number
  username: string
  email: string | null
  role: UserRole
  is_active: boolean
  locale: string
  created_at: string
  last_login_at: string | null
}

export interface AuthStatus {
  needs_setup: boolean
  authenticated: boolean
  user: CurrentUser | null
}

export interface AppSettings {
  steam_api_key_hint: string
  steam_api_key_set: boolean
  steam_id: string
  igdb_client_id: string
  igdb_client_secret_hint: string
  igdb_client_secret_set: boolean
  agent_api_key_hint: string
  agent_api_key_set: boolean
  timezone: string
  steam_configured: boolean
  igdb_configured: boolean
}

export interface SettingsUpdatePayload {
  steam_api_key?: string
  steam_id?: string
  igdb_client_id?: string
  igdb_client_secret?: string
  agent_api_key?: string
  timezone?: string
}

export interface Game {
  id: number
  name: string
  steam_app_id: number | null
  cover_url: string | null
  genres: string[]
  steam_playtime_minutes: number
  playtime_2weeks_minutes: number
  achievements_total: number
  achievements_unlocked: number
  last_played_at: string | null
}

export interface TopGame extends Game {
  tracked_seconds: number
}

export interface Summary {
  today_seconds: number
  week_seconds: number
  total_seconds: number
  sessions_week: number
  distinct_games_week: number
  active_count: number
  library_count: number
  agents_online: number
  agents_total: number
}

export interface HeatmapCell {
  weekday: number
  hour: number
  seconds: number
}

export interface HeatmapData {
  days: number
  max_seconds: number
  cells: HeatmapCell[]
}

export interface DailyPoint {
  date: string
  seconds: number
}

export interface DailyStats {
  days: number
  max_seconds: number
  items: DailyPoint[]
}

export interface GameSession {
  id: number
  game_id: number
  game_name: string
  cover_url: string | null
  source: 'agent' | 'steam'
  agent_id: string | null
  started_at: string
  ended_at: string | null
  duration_seconds: number
  is_live: boolean
}

export interface AgentInfo {
  agent_id: string
  hostname: string | null
  last_seen_at: string
  online: boolean
}
