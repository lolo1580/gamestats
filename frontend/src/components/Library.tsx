import { useMemo, useState } from 'react'
import { Clock3, LibraryBig, Search, Trophy } from 'lucide-react'
import type { Game } from '../types'
import { formatLastPlayed, formatPlaytime } from '../format'
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

    const lastPlayed = (game: Game) =>
      Math.max(
        new Date(game.last_played_at ?? 0).getTime(),
        new Date(game.xbox_last_played_at ?? 0).getTime(),
        new Date(game.ubisoft_last_played_at ?? 0).getTime(),
      )

    return [...filtered].sort((left, right) => {
      if (sort === 'name') {
        return left.name.localeCompare(right.name, lang === 'fr' ? 'fr' : 'en')
      }
      if (sort === 'recent') {
        return lastPlayed(right) - lastPlayed(left)
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
            const hasSteamAchievements = game.achievements_total > 0
            const hasXboxAchievements = game.xbox_achievements_total > 0
            const achievementsTotal = hasSteamAchievements
              ? game.achievements_total
              : hasXboxAchievements
                ? game.xbox_achievements_total
                : game.gog_achievements_total
            const achievementsUnlocked = hasSteamAchievements
              ? game.achievements_unlocked
              : hasXboxAchievements
                ? game.xbox_achievements_unlocked
                : game.gog_achievements_unlocked
            const achievementsSource = hasSteamAchievements
              ? t('library.achievementsLabel')
              : hasXboxAchievements
                ? t('library.achievementsXbox')
                : t('library.achievementsGog')
            const progress =
              achievementsTotal > 0
                ? Math.round((achievementsUnlocked / achievementsTotal) * 100)
                : 0

            return (
              <article key={game.id} className="game-card">
                <div className="game-card__media">
                  <Cover src={game.cover_url} name={game.name} className="game-cover" />
                  {(game.xbox_title_id || game.gog_product_id) && (
                    <span className="game-card__platform">
                      {[
                        game.xbox_title_id ? t('library.xboxBadge') : null,
                        game.gog_product_id ? t('library.gogBadge') : null,
                      ]
                        .filter(Boolean)
                        .join(' · ')}
                    </span>
                  )}
                  {game.steam_playtime_minutes > 0 && (
                    <span className="game-card__playtime">
                      {formatPlaytime(game.steam_playtime_minutes, lang)}
                    </span>
                  )}
                  {game.xbox_title_id && game.xbox_gamerscore > 0 && (
                    <span className="game-card__gamerscore">
                      {t('library.gamerscore', { score: game.xbox_gamerscore })}
                    </span>
                  )}
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

                  {game.ubisoft_space_id && (
                    <span className="game-card__ubisoft">
                      {t('library.ubisoftSessions', {
                        count: game.ubisoft_sessions_count,
                      })}
                      {game.ubisoft_last_played_at
                        ? ` · ${formatLastPlayed(game.ubisoft_last_played_at, lang)}`
                        : ''}
                    </span>
                  )}

                  {achievementsTotal > 0 ? (
                    <div className="achievements">
                      <div className="achievements__label">
                        <span>
                          <Trophy size={11} strokeWidth={2.2} />
                          {achievementsSource}
                        </span>
                        <span>
                          {achievementsUnlocked}/{achievementsTotal}
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
