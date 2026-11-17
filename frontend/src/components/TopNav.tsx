import {
  Gamepad2,
  History,
  LayoutDashboard,
  LibraryBig,
  Moon,
  RefreshCw,
  Sun,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { AgentInfo, Page, Summary, Theme } from '../types'
import { pluralize } from '../format'

interface TopNavProps {
  page: Page
  onNavigate: (page: Page) => void
  summary: Summary | null
  agents: AgentInfo[]
  onRefresh: () => void
  refreshing: boolean
  theme: Theme
  onThemeChange: (theme: Theme) => void
}

interface NavItem {
  id: Page
  label: string
  icon: LucideIcon
}

const NAV_ITEMS: NavItem[] = [
  { id: 'overview', label: "Vue d'ensemble", icon: LayoutDashboard },
  { id: 'library', label: 'Bibliothèque', icon: LibraryBig },
  { id: 'sessions', label: 'Sessions', icon: History },
]

export function TopNav({
  page,
  onNavigate,
  summary,
  agents,
  onRefresh,
  refreshing,
  theme,
  onThemeChange,
}: TopNavProps) {
  const onlineAgents = agents.filter((agent) => agent.online)
  const active = summary?.active_count ?? 0
  const isOnline = active > 0 || onlineAgents.length > 0
  const statusLabel =
    active > 0
      ? `${pluralize(active, 'jeu', 'jeux')} en cours`
      : onlineAgents.length > 0
        ? 'Agent en ligne'
        : 'Hors ligne'

  return (
    <header className="app-header">
      <div className="app-header__inner">
        <button
          type="button"
          className="brand"
          onClick={() => onNavigate('overview')}
          aria-label="GameStats — vue d'ensemble"
        >
          <span className="brand__logo">
            <Gamepad2 size={19} strokeWidth={2.2} />
          </span>
          <span className="brand__name">GameStats</span>
        </button>

        <nav className="header-nav" aria-label="Navigation principale">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon
            return (
              <button
                key={item.id}
                type="button"
                className={`header-nav__link${page === item.id ? ' is-active' : ''}`}
                onClick={() => onNavigate(item.id)}
                aria-current={page === item.id ? 'page' : undefined}
              >
                <Icon size={15} strokeWidth={2} />
                {item.label}
                {item.id === 'library' && summary && summary.library_count > 0 && (
                  <span className="header-nav__count">{summary.library_count}</span>
                )}
              </button>
            )
          })}
        </nav>

        <div className="header-actions">
          <div className="theme-switch" role="group" aria-label="Thème de l'interface">
            <button
              type="button"
              className={`theme-switch__button${theme === 'light' ? ' is-active' : ''}`}
              onClick={() => onThemeChange('light')}
              aria-pressed={theme === 'light'}
              aria-label="Thème clair"
              title="Thème clair"
            >
              <Sun size={15} strokeWidth={2} />
            </button>
            <button
              type="button"
              className={`theme-switch__button${theme === 'dark' ? ' is-active' : ''}`}
              onClick={() => onThemeChange('dark')}
              aria-pressed={theme === 'dark'}
              aria-label="Thème sombre"
              title="Thème sombre"
            >
              <Moon size={15} strokeWidth={2} />
            </button>
          </div>

          <span className={`status-pill${isOnline ? ' is-online' : ''}`}>
            <span className="status-pill__dot" aria-hidden="true" />
            {statusLabel}
          </span>
          <button
            type="button"
            className="button button--icon"
            onClick={onRefresh}
            disabled={refreshing}
            aria-label="Actualiser les données"
          >
            <RefreshCw
              size={16}
              strokeWidth={2}
              className={refreshing ? 'is-spinning' : undefined}
            />
            <span className="button__label">Actualiser</span>
          </button>
        </div>
      </div>
    </header>
  )
}
