import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, LoaderCircle, WifiOff } from 'lucide-react'
import { api, ApiError } from './api'
import type {
  AgentInfo,
  CurrentUser,
  DailyStats,
  Game,
  GameSession,
  HeatmapData,
  Page,
  Summary,
  Theme,
  TopGame,
} from './types'
import { useI18n } from './i18n'
import type { TranslationKey } from './i18n'
import { TopNav } from './components/TopNav'
import { StatCards } from './components/StatCards'
import { WeekChart } from './components/WeekChart'
import { LiveCard } from './components/LiveCard'
import { Heatmap } from './components/Heatmap'
import { TopGames } from './components/TopGames'
import { RecentSessions } from './components/RecentSessions'
import { SessionsPage } from './components/SessionsPage'
import { Library } from './components/Library'
import { SettingsPage } from './components/SettingsPage'
import { AuthScreen } from './components/AuthScreen'

const PAGE_META: Record<Page, { title: TranslationKey; subtitle: TranslationKey }> = {
  overview: {
    title: 'page.overview.title',
    subtitle: 'page.overview.subtitle',
  },
  library: {
    title: 'page.library.title',
    subtitle: 'page.library.subtitle',
  },
  sessions: {
    title: 'page.sessions.title',
    subtitle: 'page.sessions.subtitle',
  },
  settings: {
    title: 'page.settings.title',
    subtitle: 'page.settings.subtitle',
  },
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback
}

export default function App() {
  const { t, lang, setLang, hasStoredPreference } = useI18n()
  const [page, setPage] = useState<Page>('overview')
  const [theme, setTheme] = useState<Theme>(() =>
    document.documentElement.dataset.theme === 'light' ? 'light' : 'dark',
  )

  const [authChecked, setAuthChecked] = useState(false)
  const [needsSetup, setNeedsSetup] = useState(false)
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null)
  const [authError, setAuthError] = useState<string | null>(null)

  const [summary, setSummary] = useState<Summary | null>(null)
  const [heatmap, setHeatmap] = useState<HeatmapData | null>(null)
  const [daily, setDaily] = useState<DailyStats | null>(null)
  const [topGames, setTopGames] = useState<TopGame[]>([])
  const [sessions, setSessions] = useState<GameSession[]>([])
  const [agents, setAgents] = useState<AgentInfo[]>([])
  const [games, setGames] = useState<Game[] | null>(null)

  const [loading, setLoading] = useState(true)
  const [libraryLoading, setLibraryLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const resetData = () => {
    setSummary(null)
    setHeatmap(null)
    setDaily(null)
    setTopGames([])
    setSessions([])
    setAgents([])
    setGames(null)
    setLastUpdated(null)
  }

  const handleApiError = (apiError: unknown): boolean => {
    if (apiError instanceof ApiError && apiError.status === 401) {
      setCurrentUser(null)
      resetData()
      return true
    }
    setError(errorMessage(apiError, t('settings.error')))
    return false
  }

  useEffect(() => {
    let active = true
    api
      .authStatus()
      .then((status) => {
        if (!active) return
        setNeedsSetup(status.needs_setup)
        setCurrentUser(status.user)
        setAuthError(null)
        if (
          status.user &&
          !hasStoredPreference &&
          (status.user.locale === 'fr' || status.user.locale === 'en')
        ) {
          setLang(status.user.locale)
        }
      })
      .catch((statusError: unknown) => {
        if (active) setAuthError(errorMessage(statusError, t('settings.error')))
      })
      .finally(() => {
        if (active) setAuthChecked(true)
      })
    return () => {
      active = false
    }
    // The auth status is intentionally requested once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const loadDashboard = useCallback(async () => {
    const [nextSummary, nextHeatmap, nextDaily, nextTopGames, nextSessions, nextAgents] =
      await Promise.all([
        api.summary(),
        api.heatmap(365),
        api.daily(14),
        api.topGames(30, 6),
        api.sessions(100),
        api.agents(),
      ])

    setSummary(nextSummary)
    setHeatmap(nextHeatmap)
    setDaily(nextDaily)
    setTopGames(nextTopGames)
    setSessions(nextSessions)
    setAgents(nextAgents)
    setLastUpdated(new Date())
    setError(null)
  }, [])

  const loadLibrary = useCallback(async () => {
    setLibraryLoading(true)
    try {
      setGames(await api.games(1000))
      setError(null)
    } catch (loadError) {
      handleApiError(loadError)
    } finally {
      setLibraryLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!currentUser) return
    let active = true
    setLoading(true)
    loadDashboard()
      .catch((loadError: unknown) => {
        if (active) handleApiError(loadError)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [currentUser, loadDashboard])

  useEffect(() => {
    if (!currentUser) return
    const refresh = () => {
      if (document.visibilityState === 'visible') {
        loadDashboard().catch((loadError: unknown) => handleApiError(loadError))
      }
    }
    const timer = window.setInterval(refresh, 30_000)
    document.addEventListener('visibilitychange', refresh)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', refresh)
    }
  }, [currentUser, loadDashboard])

  useEffect(() => {
    if (currentUser && page === 'library' && games === null) {
      void loadLibrary()
    }
  }, [currentUser, page, games, loadLibrary])

  useEffect(() => {
    if (currentUser && page === 'settings' && currentUser.role !== 'admin') {
      setPage('overview')
    }
  }, [currentUser, page])

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
    document.title = `${t(PAGE_META[page].title)} — GameStats`
  }, [page, t])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute('content', theme === 'dark' ? '#0a0e14' : '#f6f7f9')
    try {
      localStorage.setItem('gamestats-theme', theme)
    } catch {
      // Stockage indisponible : le thème reste appliqué pour la session.
    }
  }, [theme])

  useEffect(() => {
    if (!currentUser || currentUser.locale === lang) return
    api
      .updateLocale(lang)
      .then((updated) => setCurrentUser(updated))
      .catch(() => {
        // The local language still applies for this session.
      })
  }, [lang, currentUser])

  const handleAuthenticated = (user: CurrentUser) => {
    setCurrentUser(user)
    setNeedsSetup(false)
    setAuthError(null)
    setPage('overview')
    if (!hasStoredPreference && (user.locale === 'fr' || user.locale === 'en')) {
      setLang(user.locale)
    }
  }

  const handleLogout = async () => {
    try {
      await api.logout()
    } finally {
      setCurrentUser(null)
      setNeedsSetup(false)
      resetData()
      setPage('overview')
    }
  }

  const handleRefresh = async () => {
    setRefreshing(true)
    setError(null)
    try {
      await loadDashboard()
      if (page === 'library') await loadLibrary()
    } catch (loadError) {
      handleApiError(loadError)
    } finally {
      setRefreshing(false)
    }
  }

  if (!authChecked) {
    return (
      <div className="auth-page">
        <div className="auth-card auth-card--loading">
          <span className="loading-state__icon">
            <LoaderCircle size={22} strokeWidth={2.2} className="is-spinning" />
          </span>
          <p>{t('page.connecting')}</p>
        </div>
      </div>
    )
  }

  if (!currentUser) {
    return (
      <AuthScreen
        needsSetup={needsSetup}
        theme={theme}
        onThemeChange={setTheme}
        onAuthenticated={handleAuthenticated}
        initialError={authError}
      />
    )
  }

  const metaTitle = t(PAGE_META[page].title)
  const metaSubtitle = t(PAGE_META[page].subtitle)
  const updatedLabel = lastUpdated
    ? t('page.updated', {
        time: lastUpdated.toLocaleTimeString(lang === 'fr' ? 'fr-FR' : 'en-US', {
          hour: '2-digit',
          minute: '2-digit',
        }),
      })
    : t('page.loading')

  return (
    <div className="app">
      <TopNav
        page={page}
        onNavigate={setPage}
        summary={summary}
        agents={agents}
        onRefresh={handleRefresh}
        refreshing={refreshing}
        theme={theme}
        onThemeChange={setTheme}
        currentUser={currentUser}
        onLogout={handleLogout}
      />

      <main className="app-main">
        <div className="page-head">
          <div>
            <h1>{metaTitle}</h1>
            <p>{metaSubtitle}</p>
          </div>
          <span className="page-head__updated">{updatedLabel}</span>
        </div>

        {error && (
          <div className="error-banner" role="alert">
            <AlertTriangle size={18} strokeWidth={2} />
            <div>
              <strong>{t('error.backendTitle')}</strong>
              <span>{error}</span>
            </div>
            <button type="button" onClick={handleRefresh} disabled={refreshing}>
              {t('common.retry')}
            </button>
          </div>
        )}

        {page === 'settings' ? (
          <SettingsPage currentUser={currentUser} />
        ) : loading && !summary ? (
          <div className="loading-state">
            <span className="loading-state__icon">
              <LoaderCircle size={22} strokeWidth={2.2} className="is-spinning" />
            </span>
            <span>{t('page.loadingActivity')}</span>
          </div>
        ) : !summary || !heatmap ? (
          <section className="panel">
            <div className="empty-state">
              <span className="empty-state__icon">
                <WifiOff size={26} strokeWidth={1.7} />
              </span>
              <strong>{t('error.unavailableTitle')}</strong>
              <p>{t('error.unavailableText')}</p>
            </div>
          </section>
        ) : page === 'overview' ? (
          <div className="page-stack">
            <StatCards summary={summary} daily={daily} />

            <div className="dashboard-grid">
              <WeekChart daily={daily} summary={summary} />
              <LiveCard summary={summary} sessions={sessions} agents={agents} />
            </div>

            <div className="dashboard-grid dashboard-grid--secondary">
              <Heatmap data={heatmap} />
              <TopGames
                games={topGames}
                days={30}
                onBrowse={() => setPage('library')}
              />
            </div>

            <RecentSessions
              sessions={sessions.slice(0, 8)}
              onViewAll={() => setPage('sessions')}
            />
          </div>
        ) : page === 'sessions' ? (
          <SessionsPage sessions={sessions} loading={loading} />
        ) : (
          <Library
            games={games ?? []}
            loading={libraryLoading || (games === null && !error)}
          />
        )}

        <footer className="app-footer">
          <span>{t('footer.selfHosted')}</span>
          <span>{updatedLabel}</span>
        </footer>
      </main>
    </div>
  )
}
