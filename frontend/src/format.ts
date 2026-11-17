import type { Language } from './i18n'

export function localeFor(lang: Language): string {
  return lang === 'fr' ? 'fr-FR' : 'en-US'
}

export function formatDuration(seconds: number, lang: Language = 'fr'): string {
  const safeSeconds = Math.max(0, Math.floor(seconds))
  const totalMinutes = Math.floor(safeSeconds / 60)
  const h = lang === 'fr' ? 'h' : 'h'
  const min = lang === 'fr' ? 'min' : 'm'

  if (totalMinutes < 1) {
    return safeSeconds > 0 ? `< 1 ${min}` : `0 ${min}`
  }

  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60

  if (lang === 'en') {
    if (hours === 0) return `${minutes} min`
    if (minutes === 0) return `${hours}h`
    return `${hours}h ${String(minutes).padStart(2, '0')}m`
  }

  if (hours === 0) return `${minutes} ${min}`
  if (minutes === 0) return `${hours} ${h}`
  return `${hours} ${h} ${String(minutes).padStart(2, '0')}`
}

export function formatCompactDuration(seconds: number, lang: Language = 'fr'): string {
  const totalMinutes = Math.floor(Math.max(0, seconds) / 60)
  if (totalMinutes < 60) return `${totalMinutes}m`

  const hours = totalMinutes / 60
  if (hours < 10) {
    const value = hours.toFixed(1).replace('.0', '')
    return `${lang === 'fr' ? value.replace('.', ',') : value}h`
  }
  return `${Math.round(hours)}h`
}

export function formatPlaytime(minutes: number, lang: Language = 'fr'): string {
  return formatDuration(Math.max(0, minutes) * 60, lang)
}

export function formatSessionStart(iso: string, lang: Language = 'fr'): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'

  const now = new Date()
  const sameDay =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()

  const time = new Intl.DateTimeFormat(localeFor(lang), {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)

  if (sameDay) {
    return lang === 'fr' ? `Aujourd'hui · ${time}` : `Today · ${time}`
  }

  return new Intl.DateTimeFormat(localeFor(lang), {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}

export function formatSessionTime(iso: string, lang: Language = 'fr'): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(localeFor(lang), {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}

export function formatLastPlayed(iso: string | null, lang: Language = 'fr'): string {
  if (!iso) return lang === 'fr' ? 'Jamais lancé' : 'Never played'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat(localeFor(lang), {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(date)
}

export function formatRelative(iso: string | null, lang: Language = 'fr'): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'

  const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000))
  if (seconds < 60) return lang === 'fr' ? "à l'instant" : 'just now'
  if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60)
    return lang === 'fr' ? `il y a ${minutes} min` : `${minutes} min ago`
  }
  if (seconds < 86_400) {
    const hours = Math.floor(seconds / 3600)
    return lang === 'fr' ? `il y a ${hours} h` : `${hours} h ago`
  }
  return new Intl.DateTimeFormat(localeFor(lang), {
    day: 'numeric',
    month: 'short',
  }).format(date)
}

export function formatDayLabel(dateKey: string, lang: Language = 'fr'): string {
  const date = new Date(`${dateKey}T12:00:00`)
  if (Number.isNaN(date.getTime())) return dateKey

  const now = new Date()
  const todayKey = localDateKey(now)
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)

  if (dateKey === todayKey) return lang === 'fr' ? "Aujourd'hui" : 'Today'
  if (dateKey === localDateKey(yesterday)) return lang === 'fr' ? 'Hier' : 'Yesterday'

  return new Intl.DateTimeFormat(localeFor(lang), {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  }).format(date)
}

export function localDateKey(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function initials(name: string): string {
  const parts = name
    .replace(/[^\p{L}\p{N} ]/gu, ' ')
    .split(/\s+/)
    .filter(Boolean)

  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
}

export function pluralize(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count > 1 ? plural : singular}`
}
