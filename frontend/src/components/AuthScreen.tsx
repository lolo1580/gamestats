import { useState } from 'react'
import type { FormEvent } from 'react'
import { Gamepad2 } from 'lucide-react'
import { api, ApiError } from '../api'
import type { CurrentUser, Theme } from '../types'
import { ThemeToggle } from './ThemeToggle'

interface AuthScreenProps {
  needsSetup: boolean
  theme: Theme
  onThemeChange: (theme: Theme) => void
  onAuthenticated: (user: CurrentUser) => void
  initialError?: string | null
}

export function AuthScreen({
  needsSetup,
  theme,
  onThemeChange,
  onAuthenticated,
  initialError = null,
}: AuthScreenProps) {
  const [identifier, setIdentifier] = useState('')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(initialError)
  const [submitting, setSubmitting] = useState(false)

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)

    if (needsSetup) {
      if (password !== confirmPassword) {
        setError('Les deux mots de passe ne correspondent pas.')
        return
      }
      if (password.length < 8) {
        setError('Le mot de passe doit contenir au moins 8 caractères.')
        return
      }
    }

    setSubmitting(true)
    try {
      const user = needsSetup
        ? await api.setup({
            username,
            email: email.trim() || null,
            password,
          })
        : await api.login({ identifier, password })
      onAuthenticated(user)
    } catch (submitError) {
      setError(
        submitError instanceof ApiError
          ? submitError.message
          : 'Impossible de contacter le backend.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-page__theme">
        <ThemeToggle theme={theme} onThemeChange={onThemeChange} />
      </div>

      <main className="auth-card">
        <div className="auth-brand">
          <span className="brand__logo">
            <Gamepad2 size={19} strokeWidth={2.2} />
          </span>
          <span>GameStats</span>
        </div>

        <span className="auth-eyebrow">
          {needsSetup ? 'Première installation' : 'Espace privé'}
        </span>
        <h1>{needsSetup ? 'Créez votre compte administrateur.' : 'Connexion.'}</h1>
        <p className="auth-intro">
          {needsSetup
            ? 'Ce compte administre le backend, les intégrations et les autres utilisateurs.'
            : 'Connectez-vous pour accéder à vos statistiques de jeu.'}
        </p>

        <form className="auth-form" onSubmit={submit}>
          {needsSetup ? (
            <>
              <label className="field">
                <span>Nom d'utilisateur</span>
                <input
                  className="input"
                  autoComplete="username"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  required
                  minLength={3}
                  pattern="[A-Za-z0-9_.-]{3,64}"
                  placeholder="laurent"
                />
              </label>
              <label className="field">
                <span>Email (optionnel)</span>
                <input
                  className="input"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="vous@exemple.fr"
                />
              </label>
            </>
          ) : (
            <label className="field">
              <span>Identifiant ou email</span>
              <input
                className="input"
                autoComplete="username"
                value={identifier}
                onChange={(event) => setIdentifier(event.target.value)}
                required
                autoFocus
                placeholder="laurent"
              />
            </label>
          )}

          <label className="field">
            <span>Mot de passe</span>
            <input
              className="input"
              type="password"
              autoComplete={needsSetup ? 'new-password' : 'current-password'}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              minLength={needsSetup ? 8 : undefined}
              placeholder="8 caractères minimum"
            />
          </label>

          {needsSetup && (
            <label className="field">
              <span>Confirmer le mot de passe</span>
              <input
                className="input"
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                required
                minLength={8}
              />
            </label>
          )}

          {error && <div className="auth-error">{error}</div>}

          <button type="submit" className="button button--primary auth-submit" disabled={submitting}>
            {submitting
              ? 'Veuillez patienter…'
              : needsSetup
                ? "Créer le compte admin"
                : 'Se connecter'}
          </button>
        </form>

        <footer className="auth-footer">
          GameStats · auto-hébergé · vos données restent locales
        </footer>
      </main>
    </div>
  )
}
