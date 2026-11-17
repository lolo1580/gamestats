import { Moon, Sun } from 'lucide-react'
import type { Theme } from '../types'
import { useI18n } from '../i18n'

interface ThemeToggleProps {
  theme: Theme
  onThemeChange: (theme: Theme) => void
}

export function ThemeToggle({ theme, onThemeChange }: ThemeToggleProps) {
  const { t } = useI18n()
  return (
    <div className="theme-switch" role="group" aria-label={t('common.lightTheme')}>
      <button
        type="button"
        className={`theme-switch__button${theme === 'light' ? ' is-active' : ''}`}
        onClick={() => onThemeChange('light')}
        aria-pressed={theme === 'light'}
        aria-label={t('common.lightTheme')}
        title={t('common.lightTheme')}
      >
        <Sun size={15} strokeWidth={2} />
      </button>
      <button
        type="button"
        className={`theme-switch__button${theme === 'dark' ? ' is-active' : ''}`}
        onClick={() => onThemeChange('dark')}
        aria-pressed={theme === 'dark'}
        aria-label={t('common.darkTheme')}
        title={t('common.darkTheme')}
      >
        <Moon size={15} strokeWidth={2} />
      </button>
    </div>
  )
}
