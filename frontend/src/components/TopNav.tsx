import { useEffect, useRef, useState } from 'react'
import {
  ChevronDown,
  Gamepad2,
  History,
  LayoutDashboard,
  LibraryBig,
  LogOut,
  RefreshCw,
  Settings,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { AgentInfo, CurrentUser, Page, Summary, Theme } from '../types'
import { initials, pluralize } from '../format'
import { ThemeToggle } from './ThemeToggle'
import { docsLinks } from '../api'

interface TopNavProps {
  page: Page
  onNavigate: (page: Page) => void
  summary: Summary | null
  agents: AgentInfo[]
  onRefresh: () => void
  refreshing: boolean
  theme: Theme
  onThemeChange: (theme: Theme) => void
  currentUser: CurrentUser
  onLogout: () => void
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
  currentUser,
  onLogout,
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

  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!menuOpen) return
    const close = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [menuOpen])

  const navigate = (next: Page) => {
    setMenuOpen(false)
    onNavigate(next)
  }

  return (
    <header className="app-header">
      <div className="app-header__inner">
        <button
          type="button"
          className="brand"
          onClick={() => navigate('overview')}
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
                onClick={() => navigate(item.id)}
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
          <ThemeToggle theme={theme} onThemeChange={onThemeChange} />

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

          <div className="user-menu" ref={menuRef}>
            <button
              type="button"
              className={`user-menu__trigger${menuOpen ? ' is-open' : ''}`}
              onClick={() => setMenuOpen((open) => !open)}
              aria-expanded={menuOpen}
              aria-haspopup="menu"
            >
              <span className="user-menu__avatar">{initials(currentUser.username)}</span>
              <span className="user-menu__name">{currentUser.username}</span>
              <ChevronDown size={13} strokeWidth={2} className="user-menu__chevron" />
            </button>

            {menuOpen && (
              <div className="user-menu__dropdown" role="menu">
                <div className="user-menu__header">
                  <strong>{currentUser.username}</strong>
                  <span>{currentUser.email || 'Aucun email'}</span>
                  <small>{currentUser.role === 'admin' ? 'Administrateur' : 'Lecteur'}</small>
                </div>

                {currentUser.role === 'admin' && (
                  <button
                    type="button"
                    className="user-menu__item"
                    role="menuitem"
                    onClick={() => navigate('settings')}
                  >
                    <Settings size={15} strokeWidth={2} />
                    Paramètres
                  </button>
                )}

                <a
                  className="user-menu__item"
                  role="menuitem"
                  href={docsLinks.swagger}
                  target="_blank"
                  rel="noreferrer"
                  onClick={() => setMenuOpen(false)}
                >
                  <span className="user-menu__item-icon">API</span>
                  Documentation API
                </a>

                <div className="user-menu__separator" />

                <button
                  type="button"
                  className="user-menu__item user-menu__item--danger"
                  role="menuitem"
                  onClick={() => {
                    setMenuOpen(false)
                    onLogout()
                  }}
                >
                  <LogOut size={15} strokeWidth={2} />
                  Déconnexion
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
