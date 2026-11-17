import type {
  AgentInfo,
  AgentRelease,
  AppSettings,
  AuthStatus,
  CurrentUser,
  DailyStats,
  EpicAuthUrl,
  EpicResult,
  Game,
  GameSession,
  GogAuthUrl,
  GogResult,
  HeatmapData,
  InfluxExportResult,
  MetadataSyncResult,
  SettingsUpdatePayload,
  Summary,
  TopGame,
  UbisoftResult,
  XboxDeviceCode,
  XboxPollResult,
  XboxSyncResult,
  UserRole,
} from './types'

const API_BASE = (import.meta.env.VITE_API_URL ?? '/api').replace(/\/$/, '')

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isFormData = init.body instanceof FormData
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: 'include',
    headers: {
      Accept: 'application/json',
      ...(init.body && !isFormData ? { 'Content-Type': 'application/json' } : {}),
      ...init.headers,
    },
  })

  if (!response.ok) {
    let detail = `Erreur ${response.status}`
    try {
      const body = (await response.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // Réponse non JSON : on garde le message générique.
    }
    throw new ApiError(detail, response.status)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

function get<T>(path: string): Promise<T> {
  return request<T>(path)
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

function patch<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

function del<T>(path: string): Promise<T> {
  return request<T>(path, { method: 'DELETE' })
}

async function download(path: string): Promise<{ blob: Blob; filename: string }> {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    headers: { Accept: 'application/octet-stream, application/json' },
  })
  if (!response.ok) {
    let detail = `Erreur ${response.status}`
    try {
      const body = (await response.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // Ignore non-JSON errors.
    }
    throw new ApiError(detail, response.status)
  }
  const disposition = response.headers.get('content-disposition') ?? ''
  const match = /filename="?([^";]+)"?/i.exec(disposition)
  return {
    blob: await response.blob(),
    filename: match?.[1] ?? 'gamestats-backup',
  }
}

function uploadBackup(
  format: 'json' | 'sqlite',
  file: File,
): Promise<{ ok: boolean; message: string }> {
  const form = new FormData()
  form.append('file', file)
  const path =
    format === 'json'
      ? '/admin/backup/import/json'
      : '/admin/backup/restore/sqlite'
  return request<{ ok: boolean; message: string }>(path, {
    method: 'POST',
    body: form,
  })
}

export const docsLinks = {
  swagger: import.meta.env.DEV ? 'http://localhost:8000/docs' : '/docs',
  redoc: import.meta.env.DEV ? 'http://localhost:8000/redoc' : '/redoc',
  readme: 'https://github.com/lolo1580/gamestats/blob/main/README.md',
}

export const api = {
  authStatus: () => get<AuthStatus>('/auth/status'),
  setup: (payload: {
    username: string
    email?: string | null
    password: string
  }) => post<CurrentUser>('/auth/setup', payload),
  login: (payload: { identifier: string; password: string }) =>
    post<CurrentUser>('/auth/login', payload),
  logout: () => post<{ ok: boolean }>('/auth/logout'),
  me: () => get<CurrentUser>('/auth/me'),
  updateLocale: (locale: 'fr' | 'en') =>
    patch<CurrentUser>('/auth/me', { locale }),
  changePassword: (payload: { current_password: string; new_password: string }) =>
    post<{ ok: boolean }>('/auth/password', payload),

  summary: () => get<Summary>('/stats/summary'),
  heatmap: (days = 365) => get<HeatmapData>(`/stats/heatmap?days=${days}`),
  daily: (days = 14) => get<DailyStats>(`/stats/daily?days=${days}`),
  topGames: (days = 30, limit = 6) =>
    get<TopGame[]>(`/stats/top-games?days=${days}&limit=${limit}`),
  sessions: (limit = 100) => get<GameSession[]>(`/sessions?limit=${limit}`),
  games: (limit = 1000) => get<Game[]>(`/games?limit=${limit}`),
  agents: () => get<AgentInfo[]>('/agents'),

  users: () => get<CurrentUser[]>('/users'),
  createUser: (payload: {
    username: string
    email?: string | null
    password: string
    role: UserRole
  }) => post<CurrentUser>('/users', payload),
  updateUser: (
    id: number,
    payload: {
      email?: string | null
      role?: UserRole
      is_active?: boolean
      password?: string
    },
  ) => patch<CurrentUser>(`/users/${id}`, payload),
  deleteUser: (id: number) => del<void>(`/users/${id}`),

  settings: () => get<AppSettings>('/settings'),
  agentRelease: () => get<AgentRelease>('/agent/release'),
  agentDownloadUrl: (kind: 'installer' | 'portable') =>
    `${API_BASE}/agent/download/${kind}`,
  updateSettings: (payload: SettingsUpdatePayload) =>
    patch<AppSettings>('/settings', payload),
  revealAgentKey: () => get<{ agent_api_key: string }>('/settings/agent-key'),
  rotateAgentKey: () => post<{ agent_api_key: string }>('/settings/agent-key/rotate'),
  revealHomepageToken: () =>
    get<{ homepage_api_token: string }>('/settings/homepage-token'),
  rotateHomepageToken: () =>
    post<{ homepage_api_token: string }>('/settings/homepage-token/rotate'),
  exportInflux: () =>
    post<InfluxExportResult>('/admin/influxdb/export'),

  startXboxDevice: () => post<XboxDeviceCode>('/xbox/device-code'),
  pollXboxDevice: () => post<XboxPollResult>('/xbox/device-code/poll'),
  syncXbox: () => post<XboxSyncResult>('/xbox/sync'),
  disconnectXbox: () => post<{ ok: boolean }>('/xbox/disconnect'),
  connectUbisoft: (rememberMeTicket: string) =>
    post<UbisoftResult>('/ubisoft/connect', {
      remember_me_ticket: rememberMeTicket,
    }),
  syncUbisoft: () => post<UbisoftResult>('/ubisoft/sync'),
  disconnectUbisoft: () => post<{ ok: boolean }>('/ubisoft/disconnect'),
  gogAuthUrl: () => get<GogAuthUrl>('/gog/auth-url'),
  connectGog: (code: string) => post<GogResult>('/gog/connect', { code }),
  syncGog: () => post<GogResult>('/gog/sync'),
  disconnectGog: () => post<{ ok: boolean }>('/gog/disconnect'),
  epicAuthUrl: () => get<EpicAuthUrl>('/epic/auth-url'),
  connectEpic: (code: string) => post<EpicResult>('/epic/connect', { code }),
  syncEpic: () => post<EpicResult>('/epic/sync'),
  disconnectEpic: () => post<{ ok: boolean }>('/epic/disconnect'),
  syncMetadata: () => post<MetadataSyncResult>('/metadata/sync'),

  downloadBackup: (format: 'json' | 'sqlite') =>
    download(`/admin/backup/export/${format}`),
  restoreBackup: (format: 'json' | 'sqlite', file: File) =>
    uploadBackup(format, file),
}
