import { useMemo, useState } from 'react'
import { Clock3, LibraryBig, Search, Trophy } from 'lucide-react'
import type { Game } from '../types'
import { formatPlaytime } from '../format'
import { useI18n } from '../i18n'
import { Cover } from './Cover'

interface LibraryProps {
  games: Game[]
  loading: boolean
}

type SortMode = 'playtime' | 'recent' | 'name'

export function Library({ games, loading }: LibraryProps) {
  const { t, lang } = useI18n()
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState<SortMode>('playtime')

  const stats = useMemo(
    () =>
      games.reduce(
        (acc, game) => ({
          minutes: acc.minutes + game.steam_playtime_minutes,
          achievementsTotal: acc.achievementsTotal + game.achievements_total,
          achievementsUnlocked: acc.achievementsUnlocked + game.achievements_unlocked,
        }),
        { minutes: 0, achievementsTotal: 0, achievementsUnlocked: 0 },
      ),
    [games],
  )

  const visibleGames = useMemo(() => {
    const term = search.trim().toLocaleLowerCase(lang === 'fr' ? 'fr' : 'en')
    const filtered = term
      ? games.filter((game) =>
          `${game.name} ${game.genres.join(' ')}`
            .toLocaleLowerCase(lang === 'fr' ? 'fr' : 'en')
            .includes(term),
        )
      : games

    return [...filtered].sort((left, right) => {
      if (sort === 'name') {
        return left.name.localeCompare(right.name, lang === 'fr' ? 'fr' : 'en')
      }
      if (sort === 'recent') {
        return (
          new Date(right.last_played_at ?? 0).getTime() -
          new Date(left.last_played_at ?? 0).getTime()
        )
      }
      return right.steam_playtime_minutes - left.steam_playtime_minutes
    })
  }, [games, search, sort, lang])

  const sortOptions: { value: SortMode; label: string }[] = [
    { value: 'playtime', label: t('library.sortTime') },
    { value: 'recent', label: t('library.sortRecent') },
    { value: 'name', label: t('library.sortName') },
  ]

  return (
    <div className="page-stack">
      <section className="panel library-panel">
        <div className="library-toolbar">
          <div className="library-metrics">
            <span>
              <LibraryBig size={15} strokeWidth={2} />
              <strong>{games.length}</strong> {t('library.games')}
            </span>
            <span>
              <Clock3 size={15} strokeWidth={2} />
              <strong>{formatPlaytime(stats.minutes, lang)}</strong> {t('library.played')}
            </span>
            <span>
              <Trophy size={15} strokeWidth={2} />
              <strong>
                {stats.achievementsUnlocked}/{stats.achievementsTotal}
              </strong>{' '}
              {t('library.achievements')}
            </span>
          </div>

          <div className="library-controls">
            <label className="search-field">
              <Search size={15} strokeWidth={2} />
              <input
                type="search"
                placeholder={t('library.search')}
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                aria-label={t('library.search')}
              />
            </label>

            <div className="segmented" role="group" aria-label={t('library.search')}>
              {sortOptions.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={`segmented__button${sort === option.value ? ' is-active' : ''}`}
                  onClick={() => setSort(option.value)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      {loading ? (
        <div className="library-grid" aria-label={t('settings.loading')}>
          {Array.from({ length: 10 }, (_, index) => (
            <span key={index} className="game-skeleton" />
          ))}
        </div>
      ) : visibleGames.length === 0 ? (
        <section className="panel">
          <div className="empty-state">
            <span className="empty-state__icon">
              <LibraryBig size={26} strokeWidth={1.7} />
            </span>
            <strong>
              {games.length === 0 ? t('library.emptyTitle') : t('library.noResults')}
            </strong>
            <p>
              {games.length === 0 ? t('library.emptyText') : t('library.noResultsText')}
            </p>
          </div>
        </section>
      ) : (
        <div className="library-grid">
          {visibleGames.map((game) => {
            const progress =
              game.achievements_total > 0
                ? Math.round((game.achievements_unlocked / game.achievements_total) * 100)
                : 0

            return (
              <article key={game.id} className="game-card">
                <div className="game-card__media">
                  <Cover src={game.cover_url} name={game.name} className="game-cover" />
                  <span className="game-card__playtime">
                    {formatPlaytime(game.steam_playtime_minutes, lang)}
                  </span>
                  {game.playtime_2weeks_minutes > 0 && (
                    <span className="game-card__recent">
                      {t('library.recentBadge', {
                        duration: formatPlaytime(game.playtime_2weeks_minutes, lang),
                      })}
                    </span>
                  )}
                </div>

                <div className="game-card__body">
                  <h3 title={game.name}>{game.name}</h3>
                  <p className="game-card__genres">
                    {game.genres.slice(0, 2).join(' · ') || t('library.unknownGenre')}
                  </p>

                  {game.achievements_total > 0 ? (
                    <div className="achievements">
                      <div className="achievements__label">
                        <span>
                          <Trophy size={11} strokeWidth={2.2} />
                          {t('library.achievementsLabel')}
                        </span>
                        <span>
                          {game.achievements_unlocked}/{game.achievements_total}
                        </span>
                      </div>
                      <div className="achievements__bar" aria-hidden="true">
                        <span style={{ width: `${progress}%` }} />
                      </div>
                    </div>
                  ) : (
                    <span className="game-card__empty">{t('library.noAchievements')}</span>
                  )}
                </div>
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}
