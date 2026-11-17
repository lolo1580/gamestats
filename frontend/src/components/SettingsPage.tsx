import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import {
  BookOpen,
  Check,
  Copy,
  ExternalLink,
  Eye,
  EyeOff,
  KeyRound,
  RefreshCw,
  Save,
  Server,
  Shield,
  Trash2,
  UserPlus,
  Users,
  Wifi,
} from 'lucide-react'
import { api, ApiError, docsLinks } from '../api'
import type {
  AppSettings,
  CurrentUser,
  SettingsUpdatePayload,
  UserRole,
} from '../types'
import { formatRelative } from '../format'

type SettingsTab = 'general' | 'integrations' | 'users' | 'account' | 'docs'

interface SettingsPageProps {
  currentUser: CurrentUser
}

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : 'Une erreur est survenue.'
}

async function copyToClipboard(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()
  document.execCommand('copy')
  document.body.removeChild(textarea)
}

export function SettingsPage({ currentUser }: SettingsPageProps) {
  const [tab, setTab] = useState<SettingsTab>('general')
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [users, setUsers] = useState<CurrentUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const [timezone, setTimezone] = useState('Europe/Paris')
  const [steamId, setSteamId] = useState('')
  const [steamKey, setSteamKey] = useState('')
  const [igdbClientId, setIgdbClientId] = useState('')
  const [igdbSecret, setIgdbSecret] = useState('')
  const [revealedAgentKey, setRevealedAgentKey] = useState<string | null>(null)

  const [newUsername, setNewUsername] = useState('')
  const [newEmail, setNewEmail] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newRole, setNewRole] = useState<UserRole>('viewer')
  const [resetUserId, setResetUserId] = useState<number | null>(null)
  const [resetPassword, setResetPassword] = useState('')

  const [currentPassword, setCurrentPassword] = useState('')
  const [accountPassword, setAccountPassword] = useState('')
  const [accountConfirm, setAccountConfirm] = useState('')

  const [saving, setSaving] = useState(false)
  const [creatingUser, setCreatingUser] = useState(false)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [nextSettings, nextUsers] = await Promise.all([
        api.settings(),
        api.users(),
      ])
      setSettings(nextSettings)
      setUsers(nextUsers)
      setTimezone(nextSettings.timezone)
      setSteamId(nextSettings.steam_id)
      setIgdbClientId(nextSettings.igdb_client_id)
    } catch (loadError) {
      setError(errorMessage(loadError))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const flash = (text: string) => {
    setMessage(text)
    window.setTimeout(() => setMessage(null), 4000)
  }

  const saveGeneral = async (event: FormEvent) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const next = await api.updateSettings({ timezone })
      setSettings(next)
      setTimezone(next.timezone)
      flash('Paramètres généraux enregistrés.')
    } catch (saveError) {
      setError(errorMessage(saveError))
    } finally {
      setSaving(false)
    }
  }

  const saveIntegrations = async (event: FormEvent) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const payload: SettingsUpdatePayload = {
        steam_id: steamId.trim(),
        igdb_client_id: igdbClientId.trim(),
      }
      if (steamKey.trim()) payload.steam_api_key = steamKey.trim()
      if (igdbSecret.trim()) payload.igdb_client_secret = igdbSecret.trim()

      const next = await api.updateSettings(payload)
      setSettings(next)
      setSteamKey('')
      setIgdbSecret('')
      flash('Intégrations enregistrées.')
    } catch (saveError) {
      setError(errorMessage(saveError))
    } finally {
      setSaving(false)
    }
  }

  const clearSecret = async (field: 'steam_api_key' | 'igdb_client_secret') => {
    if (!window.confirm('Supprimer ce secret ?')) return
    setSaving(true)
    setError(null)
    try {
      const next = await api.updateSettings({ [field]: '' })
      setSettings(next)
      flash('Secret supprimé.')
    } catch (saveError) {
      setError(errorMessage(saveError))
    } finally {
      setSaving(false)
    }
  }

  const revealAgentKey = async () => {
    if (revealedAgentKey) {
      setRevealedAgentKey(null)
      return
    }
    try {
      const result = await api.revealAgentKey()
      setRevealedAgentKey(result.agent_api_key)
    } catch (revealError) {
      setError(errorMessage(revealError))
    }
  }

  const copyAgentKey = async () => {
    try {
      const key = revealedAgentKey ?? (await api.revealAgentKey()).agent_api_key
      setRevealedAgentKey(key)
      await copyToClipboard(key)
      flash('Clé agent copiée.')
    } catch (copyError) {
      setError(errorMessage(copyError))
    }
  }

  const rotateAgentKey = async () => {
    if (
      !window.confirm(
        "Générer une nouvelle clé ? L'agent devra être mis à jour immédiatement.",
      )
    ) {
      return
    }
    setSaving(true)
    setError(null)
    try {
      const result = await api.rotateAgentKey()
      setRevealedAgentKey(result.agent_api_key)
      const next = await api.settings()
      setSettings(next)
      flash("Nouvelle clé générée. Copiez-la dans l'agent.")
    } catch (rotateError) {
      setError(errorMessage(rotateError))
    } finally {
      setSaving(false)
    }
  }

  const createUser = async (event: FormEvent) => {
    event.preventDefault()
    setCreatingUser(true)
    setError(null)
    try {
      await api.createUser({
        username: newUsername,
        email: newEmail.trim() || null,
        password: newPassword,
        role: newRole,
      })
      setNewUsername('')
      setNewEmail('')
      setNewPassword('')
      setNewRole('viewer')
      setUsers(await api.users())
      flash('Utilisateur créé.')
    } catch (createError) {
      setError(errorMessage(createError))
    } finally {
      setCreatingUser(false)
    }
  }

  const updateUser = async (
    id: number,
    payload: { role?: UserRole; is_active?: boolean; password?: string },
  ) => {
    setError(null)
    try {
      await api.updateUser(id, payload)
      setUsers(await api.users())
      flash('Utilisateur mis à jour.')
    } catch (updateError) {
      setError(errorMessage(updateError))
    }
  }

  const deleteUser = async (user: CurrentUser) => {
    if (!window.confirm(`Supprimer le compte « ${user.username} » ?`)) return
    setError(null)
    try {
      await api.deleteUser(user.id)
      setUsers(await api.users())
      flash('Utilisateur supprimé.')
    } catch (deleteError) {
      setError(errorMessage(deleteError))
    }
  }

  const changeAccountPassword = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    if (accountPassword !== accountConfirm) {
      setError('Les deux mots de passe ne correspondent pas.')
      return
    }
    try {
      await api.changePassword({
        current_password: currentPassword,
        new_password: accountPassword,
      })
      setCurrentPassword('')
      setAccountPassword('')
      setAccountConfirm('')
      flash('Mot de passe modifié.')
    } catch (passwordError) {
      setError(errorMessage(passwordError))
    }
  }

  const tabs: { id: SettingsTab; label: string; icon: typeof Users }[] = [
    { id: 'general', label: 'Général', icon: Server },
    { id: 'integrations', label: 'Intégrations', icon: Wifi },
    { id: 'users', label: 'Utilisateurs', icon: Users },
    { id: 'account', label: 'Mon compte', icon: Shield },
    { id: 'docs', label: 'Documentation', icon: BookOpen },
  ]

  if (loading) {
    return (
      <div className="loading-state">
        <span className="loading-state__icon">
          <RefreshCw size={22} strokeWidth={2.2} className="is-spinning" />
        </span>
        <span>Chargement des paramètres…</span>
      </div>
    )
  }

  return (
    <div className="settings-page">
      <div className="settings-tabs" role="tablist" aria-label="Sections des paramètres">
        {tabs.map((item) => {
          const Icon = item.icon
          return (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={tab === item.id}
              className={`settings-tab${tab === item.id ? ' is-active' : ''}`}
              onClick={() => setTab(item.id)}
            >
              <Icon size={15} strokeWidth={2} />
              {item.label}
            </button>
          )
        })}
      </div>

      {error && <div className="settings-alert is-error">{error}</div>}
      {message && (
        <div className="settings-alert is-success">
          <Check size={15} strokeWidth={2.2} />
          {message}
        </div>
      )}

      {tab === 'general' && settings && (
        <div className="settings-grid">
          <section className="panel settings-panel">
            <header className="card-head">
              <div>
                <h2>Général</h2>
                <p>Fuseau horaire utilisé par les statistiques.</p>
              </div>
            </header>
            <form className="settings-form" onSubmit={saveGeneral}>
              <label className="field">
                <span>Fuseau horaire</span>
                <input
                  className="input"
                  value={timezone}
                  onChange={(event) => setTimezone(event.target.value)}
                  placeholder="Europe/Paris"
                  required
                />
                <small>Exemple : Europe/Paris, Europe/London, America/New_York.</small>
              </label>
              <button type="submit" className="button button--primary" disabled={saving}>
                <Save size={15} strokeWidth={2} />
                Enregistrer
              </button>
            </form>
          </section>

          <section className="panel settings-panel">
            <header className="card-head">
              <div>
                <h2>Clé agent</h2>
                <p>Secret utilisé par le tracker Windows pour envoyer les heartbeats.</p>
              </div>
              <span
                className={`config-status${settings.agent_api_key_set ? ' is-on' : ' is-off'}`}
              >
                {settings.agent_api_key_set ? 'Configurée' : 'Absente'}
              </span>
            </header>

            <div className="agent-key">
              <code>{revealedAgentKey ?? settings.agent_api_key_hint ?? 'Non définie'}</code>
              <button
                type="button"
                className="button button--icon"
                onClick={revealAgentKey}
                aria-label={revealedAgentKey ? 'Masquer la clé' : 'Afficher la clé'}
                title={revealedAgentKey ? 'Masquer' : 'Afficher'}
              >
                {revealedAgentKey ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
              <button
                type="button"
                className="button button--icon"
                onClick={copyAgentKey}
                aria-label="Copier la clé"
                title="Copier"
              >
                <Copy size={15} />
              </button>
            </div>

            <div className="settings-actions">
              <button
                type="button"
                className="button"
                onClick={rotateAgentKey}
                disabled={saving}
              >
                <RefreshCw size={14} strokeWidth={2} />
                Régénérer la clé
              </button>
            </div>
            <p className="settings-hint">
              Endpoint de l'agent : <code>{window.location.origin}/api/heartbeat</code>
            </p>
          </section>
        </div>
      )}

      {tab === 'integrations' && settings && (
        <section className="panel settings-panel">
          <header className="card-head">
            <div>
              <h2>Intégrations</h2>
              <p>Steam et IGDB. Les secrets sont masqués et ne sont jamais renvoyés en clair.</p>
            </div>
          </header>

          <form className="settings-form" onSubmit={saveIntegrations}>
            <div className="settings-group">
              <div className="settings-group__head">
                <h3>Steam</h3>
                <span
                  className={`config-status${settings.steam_configured ? ' is-on' : ' is-off'}`}
                >
                  {settings.steam_configured ? 'Configuré' : 'Non configuré'}
                </span>
              </div>
              <div className="form-grid">
                <label className="field">
                  <span>Clé API Steam</span>
                  <input
                    className="input"
                    type="password"
                    value={steamKey}
                    onChange={(event) => setSteamKey(event.target.value)}
                    placeholder={
                      settings.steam_api_key_set
                        ? settings.steam_api_key_hint
                        : 'Laisser vide pour conserver'
                    }
                    autoComplete="off"
                  />
                </label>
                <label className="field">
                  <span>SteamID64</span>
                  <input
                    className="input"
                    value={steamId}
                    onChange={(event) => setSteamId(event.target.value)}
                    placeholder="7656119…"
                    inputMode="numeric"
                  />
                </label>
              </div>
              {settings.steam_api_key_set && (
                <button
                  type="button"
                  className="text-button text-button--danger"
                  onClick={() => clearSecret('steam_api_key')}
                >
                  Supprimer la clé Steam
                </button>
              )}
            </div>

            <div className="settings-group">
              <div className="settings-group__head">
                <h3>IGDB</h3>
                <span
                  className={`config-status${settings.igdb_configured ? ' is-on' : ' is-off'}`}
                >
                  {settings.igdb_configured ? 'Configuré' : 'Non configuré'}
                </span>
              </div>
              <div className="form-grid">
                <label className="field">
                  <span>Client ID</span>
                  <input
                    className="input"
                    value={igdbClientId}
                    onChange={(event) => setIgdbClientId(event.target.value)}
                    autoComplete="off"
                  />
                </label>
                <label className="field">
                  <span>Client secret</span>
                  <input
                    className="input"
                    type="password"
                    value={igdbSecret}
                    onChange={(event) => setIgdbSecret(event.target.value)}
                    placeholder={
                      settings.igdb_client_secret_set
                        ? settings.igdb_client_secret_hint
                        : 'Laisser vide pour conserver'
                    }
                    autoComplete="off"
                  />
                </label>
              </div>
              {settings.igdb_client_secret_set && (
                <button
                  type="button"
                  className="text-button text-button--danger"
                  onClick={() => clearSecret('igdb_client_secret')}
                >
                  Supprimer le secret IGDB
                </button>
              )}
            </div>

            <button type="submit" className="button button--primary" disabled={saving}>
              <Save size={15} strokeWidth={2} />
              Enregistrer les intégrations
            </button>
          </form>
        </section>
      )}

      {tab === 'users' && (
        <div className="settings-stack">
          <section className="panel settings-panel">
            <header className="card-head">
              <div>
                <h2>Ajouter un utilisateur</h2>
                <p>Les lecteurs peuvent consulter le dashboard, sans accéder aux paramètres.</p>
              </div>
            </header>
            <form className="user-create-form" onSubmit={createUser}>
              <label className="field">
                <span>Nom d'utilisateur</span>
                <input
                  className="input"
                  value={newUsername}
                  onChange={(event) => setNewUsername(event.target.value)}
                  required
                  minLength={3}
                />
              </label>
              <label className="field">
                <span>Email (optionnel)</span>
                <input
                  className="input"
                  type="email"
                  value={newEmail}
                  onChange={(event) => setNewEmail(event.target.value)}
                />
              </label>
              <label className="field">
                <span>Mot de passe</span>
                <input
                  className="input"
                  type="password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  required
                  minLength={8}
                />
              </label>
              <label className="field">
                <span>Rôle</span>
                <select
                  className="select"
                  value={newRole}
                  onChange={(event) => setNewRole(event.target.value as UserRole)}
                >
                  <option value="viewer">Lecteur</option>
                  <option value="admin">Administrateur</option>
                </select>
              </label>
              <button
                type="submit"
                className="button button--primary"
                disabled={creatingUser}
              >
                <UserPlus size={15} strokeWidth={2} />
                Créer
              </button>
            </form>
          </section>

          <section className="panel settings-panel">
            <header className="card-head">
              <div>
                <h2>Comptes</h2>
                <p>{users.length} utilisateur(s) enregistré(s).</p>
              </div>
            </header>

            <div className="users-table">
              <div className="users-table__head">
                <span>Utilisateur</span>
                <span>Rôle</span>
                <span>Statut</span>
                <span>Dernière connexion</span>
                <span />
              </div>
              {users.map((user) => {
                const self = user.id === currentUser.id
                return (
                  <div key={user.id} className="user-row-wrap">
                    <div className="users-table__row">
                      <div className="user-identity">
                        <span className="user-avatar">
                          {user.username.slice(0, 2).toUpperCase()}
                        </span>
                        <div>
                          <strong>{user.username}{self ? ' (vous)' : ''}</strong>
                          <span>{user.email || 'Pas d’email'}</span>
                        </div>
                      </div>
                      <select
                        className="select select--small"
                        value={user.role}
                        disabled={self}
                        onChange={(event) =>
                          updateUser(user.id, { role: event.target.value as UserRole })
                        }
                      >
                        <option value="viewer">Lecteur</option>
                        <option value="admin">Admin</option>
                      </select>
                      <span
                        className={`config-status${user.is_active ? ' is-on' : ' is-off'}`}
                      >
                        {user.is_active ? 'Actif' : 'Désactivé'}
                      </span>
                      <span className="user-last-login">
                        {user.last_login_at ? formatRelative(user.last_login_at) : 'Jamais'}
                      </span>
                      <div className="user-actions">
                        <button
                          type="button"
                          className="button button--icon"
                          title={user.is_active ? 'Désactiver' : 'Activer'}
                          aria-label={user.is_active ? 'Désactiver' : 'Activer'}
                          disabled={self}
                          onClick={() =>
                            updateUser(user.id, { is_active: !user.is_active })
                          }
                        >
                          <Eye size={14} />
                        </button>
                        <button
                          type="button"
                          className="button button--icon"
                          title="Réinitialiser le mot de passe"
                          aria-label="Réinitialiser le mot de passe"
                          disabled={self}
                          onClick={() => {
                            setResetUserId(resetUserId === user.id ? null : user.id)
                            setResetPassword('')
                          }}
                        >
                          <KeyRound size={14} />
                        </button>
                        <button
                          type="button"
                          className="button button--icon button--danger"
                          title="Supprimer"
                          aria-label="Supprimer"
                          disabled={self}
                          onClick={() => deleteUser(user)}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>

                    {resetUserId === user.id && (
                      <form
                        className="reset-password-row"
                        onSubmit={async (event) => {
                          event.preventDefault()
                          await updateUser(user.id, { password: resetPassword })
                          setResetUserId(null)
                          setResetPassword('')
                        }}
                      >
                        <input
                          className="input"
                          type="password"
                          value={resetPassword}
                          onChange={(event) => setResetPassword(event.target.value)}
                          placeholder="Nouveau mot de passe (8 caractères min.)"
                          minLength={8}
                          required
                        />
                        <button type="submit" className="button button--primary">
                          Appliquer
                        </button>
                      </form>
                    )}
                  </div>
                )
              })}
            </div>
          </section>
        </div>
      )}

      {tab === 'account' && (
        <section className="panel settings-panel settings-panel--narrow">
          <header className="card-head">
            <div>
              <h2>Mon compte</h2>
              <p>Connecté en tant que {currentUser.username}.</p>
            </div>
          </header>
          <form className="settings-form" onSubmit={changeAccountPassword}>
            <label className="field">
              <span>Mot de passe actuel</span>
              <input
                className="input"
                type="password"
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
                autoComplete="current-password"
                required
              />
            </label>
            <div className="form-grid">
              <label className="field">
                <span>Nouveau mot de passe</span>
                <input
                  className="input"
                  type="password"
                  value={accountPassword}
                  onChange={(event) => setAccountPassword(event.target.value)}
                  autoComplete="new-password"
                  minLength={8}
                  required
                />
              </label>
              <label className="field">
                <span>Confirmer</span>
                <input
                  className="input"
                  type="password"
                  value={accountConfirm}
                  onChange={(event) => setAccountConfirm(event.target.value)}
                  autoComplete="new-password"
                  minLength={8}
                  required
                />
              </label>
            </div>
            <button type="submit" className="button button--primary">
              <Save size={15} strokeWidth={2} />
              Modifier le mot de passe
            </button>
          </form>
        </section>
      )}

      {tab === 'docs' && (
        <div className="settings-stack">
          <section className="panel settings-panel">
            <header className="card-head">
              <div>
                <h2>Documentation API</h2>
                <p>Les pages de documentation sont protégées par votre session.</p>
              </div>
            </header>
            <div className="docs-links">
              <a href={docsLinks.swagger} target="_blank" rel="noreferrer">
                <BookOpen size={17} strokeWidth={2} />
                <span>
                  <strong>Swagger UI</strong>
                  <small>Tester les endpoints</small>
                </span>
                <ExternalLink size={14} />
              </a>
              <a href={docsLinks.redoc} target="_blank" rel="noreferrer">
                <BookOpen size={17} strokeWidth={2} />
                <span>
                  <strong>ReDoc</strong>
                  <small>Référence lisible</small>
                </span>
                <ExternalLink size={14} />
              </a>
              <a href={docsLinks.readme} target="_blank" rel="noreferrer">
                <BookOpen size={17} strokeWidth={2} />
                <span>
                  <strong>README</strong>
                  <small>Installation et intégrations</small>
                </span>
                <ExternalLink size={14} />
              </a>
            </div>
          </section>

          <section className="panel settings-panel">
            <header className="card-head">
              <div>
                <h2>Agent Windows</h2>
                <p>Configuration du tracker local.</p>
              </div>
            </header>
            <div className="docs-code">
              <code>POST {window.location.origin}/api/heartbeat</code>
              <code>Header X-Agent-Key: &lt;clé agent&gt;</code>
            </div>
            <p className="settings-hint">
              La clé agent se gère dans l'onglet Général. Ne la partagez pas et ne
              l'exposez pas dans un dépôt.
            </p>
          </section>
        </div>
      )}
    </div>
  )
}
