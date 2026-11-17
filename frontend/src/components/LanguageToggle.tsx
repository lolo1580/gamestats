import { useI18n } from '../i18n'

export function LanguageToggle() {
  const { lang, setLang, t } = useI18n()
  return (
    <button
      type="button"
      className="button button--icon lang-toggle"
      onClick={() => setLang(lang === 'fr' ? 'en' : 'fr')}
      title={t('common.switchLanguage')}
      aria-label={t('common.switchLanguage')}
    >
      <span>{lang.toUpperCase()}</span>
    </button>
  )
}
