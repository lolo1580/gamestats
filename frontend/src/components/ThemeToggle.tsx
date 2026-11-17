import { Moon, Sun } from 'lucide-react'
import type { Theme } from '../types'

interface ThemeToggleProps {
  theme: Theme
  onThemeChange: (theme: Theme) => void
}

export function ThemeToggle({ theme, onThemeChange }: ThemeToggleProps) {
  return (
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
  )
}
