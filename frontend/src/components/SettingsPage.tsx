import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import {
  AlertTriangle,
  BookOpen,
  Check,
  Copy,
  Database,
  Download,
  ExternalLink,
  Eye,
  EyeOff,
  Globe2,
  KeyRound,
  RefreshCw,
  Save,
  Server,
  Shield,
  Trash2,
  Upload,
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
import { useI18n } from '../i18n'
import type { TranslationKey } from '../i18n'

type SettingsTab = 'general' | 'integrations' | 'users' | 'account' | 'backup' | 'docs'
type BackupBusy = 'download-json' | 'download-sqlite' | 'upload-json' | 'upload-sqlite' | null

interface SettingsPageProps {
  currentUser: CurrentUser
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
  const { t, lang } = useI18n()
  const [tab, setTab] = useState<SettingsTab>('general')
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [users, setUsers] = useState<CurrentUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [backupBusy, setBackupBusy] = useState<BackupBusy>(null)

  const [timezone, setTimezone] = useState('Europe/Paris')
  const [steamId, setSteamId] = useState('')
  const [steamKey, setSteamKey] = useState('')
  const [igdbClientId, setIgdbClientId] = useState('')
  const [igdbSecret, setIgdbSecret] = useState('')
  const [revealedAgentKey, setRevealedAgentKey] = useState<string | null>(null)
  const [revealedHomepageToken, setRevealedHomepageToken] = useState<string | null>(null)
  const [influxUrl, setInfluxUrl] = useState('')
  const [influxToken, setInfluxToken] = useState('')
  const [influxOrg, setInfluxOrg] = useState('')
  const [influxBucket, setInfluxBucket] = useState('')
  const [influxEnabled, setInfluxEnabled] = useState(false)
  const [influxBusy, setInfluxBusy] = useState(false)
  const [xboxClientId, setXboxClientId] = useState('')
  const [xboxDevice, setXboxDevice] = useState<{
    user_code: string
    verification_uri: string
    expires_in: number
    interval: number
  } | null>(null)
  const [xboxBusy, setXboxBusy] = useState(false)
  const [ubisoftTicket, setUbisoftTicket] = useState('')
  const [ubisoftBusy, setUbisoftBusy] = useState(false)
  const [gogCode, setGogCode] = useState('')
  const [gogBusy, setGogBusy] = useState(false)
  const [gogAuthUrl, setGogAuthUrl] = useState<string | null>(null)
  const [epicCode, setEpicCode] = useState('')
  const [epicBusy, setEpicBusy] = useState(false)
  const [epicAuthUrl, setEpicAuthUrl] = useState<string | null>(null)
  const [mobygamesKey, setMobygamesKey] = useState('')
  const [opencriticKey, setOpencriticKey] = useState('')
  const [hltbEnabled, setHltbEnabled] = useState(true)
  const [metadataBusy, setMetadataBusy] = useState(false)

  const [newUsername, setNewUsername] = useState('')
  const [newEmail, setNewEmail] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newRole, setNewRole] = useState<UserRole>('viewer')
  const [resetUserId, setResetUserId] = useState<number | null>(null)
  const [resetPassword, setResetPassword] = useState('')

  const [currentPassword, setCurrentPassword] = useState('')
  const [accountPassword, setAccountPassword] = useState('')
  const [accountConfirm, setAccountConfirm] = useState('')

  const jsonInputRef = useRef<HTMLInputElement>(null)
  const sqliteInputRef = useRef<HTMLInputElement>(null)

  const reportError = (value: unknown) => {
    setError(value instanceof ApiError ? value.message : t('settings.error'))
  }

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [nextSettings, nextUsers, gogAuth, epicAuth] = await Promise.all([
        api.settings(),
        api.users(),
        api.gogAuthUrl().catch(() => null),
        api.epicAuthUrl().catch(() => null),
      ])
      setSettings(nextSettings)
      setUsers(nextUsers)
      if (gogAuth) setGogAuthUrl(gogAuth.url)
      if (epicAuth) setEpicAuthUrl(epicAuth.url)
      setTimezone(nextSettings.timezone)
      setSteamId(nextSettings.steam_id)
      setIgdbClientId(nextSettings.igdb_client_id)
      setInfluxUrl(nextSettings.influxdb_url)
      setInfluxOrg(nextSettings.influxdb_org)
      setInfluxBucket(nextSettings.influxdb_bucket)
      setInfluxEnabled(nextSettings.influxdb_enabled)
      setXboxClientId(nextSettings.xbox_client_id)
      setHltbEnabled(nextSettings.hltb_enabled)
    } catch (loadError) {
      reportError(loadError)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
    // Load once when the settings page is opened.
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
      flash(t('settings.savedGeneral'))
    } catch (saveError) {
      reportError(saveError)
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
        influxdb_url: influxUrl.trim(),
        influxdb_org: influxOrg.trim(),
        influxdb_bucket: influxBucket.trim(),
        influxdb_enabled: influxEnabled,
        xbox_client_id: xboxClientId.trim(),
        hltb_enabled: hltbEnabled,
      }
      if (steamKey.trim()) payload.steam_api_key = steamKey.trim()
      if (igdbSecret.trim()) payload.igdb_client_secret = igdbSecret.trim()
      if (influxToken.trim()) payload.influxdb_token = influxToken.trim()
      if (mobygamesKey.trim()) payload.mobygames_api_key = mobygamesKey.trim()
      if (opencriticKey.trim()) payload.opencritic_api_key = opencriticKey.trim()

      const next = await api.updateSettings(payload)
      setSettings(next)
      setSteamKey('')
      setIgdbSecret('')
      setInfluxToken('')
      setMobygamesKey('')
      setOpencriticKey('')
      setInfluxUrl(next.influxdb_url)
      setInfluxOrg(next.influxdb_org)
      setInfluxBucket(next.influxdb_bucket)
      setInfluxEnabled(next.influxdb_enabled)
      setXboxClientId(next.xbox_client_id)
      setHltbEnabled(next.hltb_enabled)
      flash(t('settings.integrations.saved'))
    } catch (saveError) {
      reportError(saveError)
    } finally {
      setSaving(false)
    }
  }

  const clearSecret = async (field: 'steam_api_key' | 'igdb_client_secret') => {
    if (!window.confirm(t('settings.integrations.confirmDelete'))) return
    setSaving(true)
    setError(null)
    try {
      const next = await api.updateSettings({ [field]: '' })
      setSettings(next)
      flash(t('settings.integrations.secretDeleted'))
    } catch (saveError) {
      reportError(saveError)
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
      reportError(revealError)
    }
  }

  const copyAgentKey = async () => {
    try {
      const key = revealedAgentKey ?? (await api.revealAgentKey()).agent_api_key
      setRevealedAgentKey(key)
      await copyToClipboard(key)
      flash(t('settings.agent.copied'))
    } catch (copyError) {
      reportError(copyError)
    }
  }

  const rotateAgentKey = async () => {
    if (!window.confirm(t('settings.agent.rotateConfirm'))) return
    setSaving(true)
    setError(null)
    try {
      const result = await api.rotateAgentKey()
      setRevealedAgentKey(result.agent_api_key)
      setSettings(await api.settings())
      flash(t('settings.agent.rotated'))
    } catch (rotateError) {
      reportError(rotateError)
    } finally {
      setSaving(false)
    }
  }

  const revealHomepageToken = async () => {
    if (revealedHomepageToken) {
      setRevealedHomepageToken(null)
      return
    }
    try {
      const result = await api.revealHomepageToken()
      setRevealedHomepageToken(result.homepage_api_token)
    } catch (tokenError) {
      reportError(tokenError)
    }
  }

  const copyHomepageToken = async () => {
    try {
      const token =
        revealedHomepageToken ??
        (await api.revealHomepageToken()).homepage_api_token
      setRevealedHomepageToken(token)
      await copyToClipboard(token)
      flash(t('settings.integrations.homepageCopied'))
    } catch (copyError) {
      reportError(copyError)
    }
  }

  const rotateHomepageToken = async () => {
    if (!window.confirm(t('settings.integrations.homepageRotateConfirm'))) return
    setSaving(true)
    setError(null)
    try {
      const result = await api.rotateHomepageToken()
      setRevealedHomepageToken(result.homepage_api_token)
      setSettings(await api.settings())
      flash(t('settings.integrations.homepageRotated'))
    } catch (tokenError) {
      reportError(tokenError)
    } finally {
      setSaving(false)
    }
  }

  const exportInfluxNow = async () => {
    setInfluxBusy(true)
    setError(null)
    try {
      const result = await api.exportInflux()
      if (result.skipped) {
        flash(t('settings.integrations.influxSkipped'))
      } else {
        flash(
          t('settings.integrations.influxExported', {
            sessions: result.sessions_exported ?? 0,
            points: result.points_written ?? 0,
          }),
        )
      }
      setSettings(await api.settings())
    } catch (exportError) {
      reportError(exportError)
    } finally {
      setInfluxBusy(false)
    }
  }

  const startXboxConnection = async () => {
    if (!settings?.xbox_client_id) {
      setError(t('settings.integrations.xboxSaveFirst'))
      return
    }
    setXboxBusy(true)
    setError(null)
    try {
      setXboxDevice(await api.startXboxDevice())
    } catch (xboxError) {
      reportError(xboxError)
    } finally {
      setXboxBusy(false)
    }
  }

  const syncXboxNow = async () => {
    setXboxBusy(true)
    setError(null)
    try {
      const result = await api.syncXbox()
      setSettings(await api.settings())
      if (result.skipped) {
        flash(result.reason ?? t('settings.integrations.xboxError'))
      } else {
        flash(
          t('settings.integrations.xboxSynced', {
            titles: result.titles_synced ?? 0,
          }),
        )
      }
    } catch (xboxError) {
      reportError(xboxError)
    } finally {
      setXboxBusy(false)
    }
  }

  const disconnectXbox = async () => {
    if (!window.confirm(t('settings.integrations.xboxDisconnectConfirm'))) return
    setXboxBusy(true)
    setError(null)
    try {
      await api.disconnectXbox()
      setSettings(await api.settings())
      setXboxDevice(null)
      flash(t('settings.integrations.xboxNotConnected'))
    } catch (xboxError) {
      reportError(xboxError)
    } finally {
      setXboxBusy(false)
    }
  }

  const connectUbisoft = async () => {
    if (!ubisoftTicket.trim()) {
      setError(t('settings.integrations.ubisoftTicketHint'))
      return
    }
    setUbisoftBusy(true)
    setError(null)
    try {
      const result = await api.connectUbisoft(ubisoftTicket.trim())
      setUbisoftTicket('')
      setSettings(await api.settings())
      flash(
        result.message ??
          t('settings.integrations.ubisoftSynced', {
            games: result.games_synced ?? 0,
          }),
      )
    } catch (ubisoftError) {
      reportError(ubisoftError)
    } finally {
      setUbisoftBusy(false)
    }
  }

  const syncUbisoftNow = async () => {
    setUbisoftBusy(true)
    setError(null)
    try {
      const result = await api.syncUbisoft()
      setSettings(await api.settings())
      flash(
        result.message ??
          t('settings.integrations.ubisoftSynced', {
            games: result.games_synced ?? 0,
          }),
      )
    } catch (ubisoftError) {
      reportError(ubisoftError)
    } finally {
      setUbisoftBusy(false)
    }
  }

  const disconnectUbisoft = async () => {
    if (!window.confirm(t('settings.integrations.ubisoftDisconnectConfirm'))) return
    setUbisoftBusy(true)
    setError(null)
    try {
      await api.disconnectUbisoft()
      setSettings(await api.settings())
      flash(t('settings.integrations.ubisoftNotConnected'))
    } catch (ubisoftError) {
      reportError(ubisoftError)
    } finally {
      setUbisoftBusy(false)
    }
  }

  const connectGog = async () => {
    if (!gogCode.trim()) {
      setError(t('settings.integrations.gogCodeHint'))
      return
    }
    setGogBusy(true)
    setError(null)
    try {
      const result = await api.connectGog(gogCode.trim())
      setGogCode('')
      setSettings(await api.settings())
      flash(
        result.message ??
          t('settings.integrations.gogSynced', {
            games: result.games_synced ?? 0,
          }),
      )
    } catch (gogError) {
      reportError(gogError)
    } finally {
      setGogBusy(false)
    }
  }

  const syncGogNow = async () => {
    setGogBusy(true)
    setError(null)
    try {
      const result = await api.syncGog()
      setSettings(await api.settings())
      flash(
        result.message ??
          t('settings.integrations.gogSynced', {
            games: result.games_synced ?? 0,
          }),
      )
    } catch (gogError) {
      reportError(gogError)
    } finally {
      setGogBusy(false)
    }
  }

  const disconnectGog = async () => {
    if (!window.confirm(t('settings.integrations.gogDisconnectConfirm'))) return
    setGogBusy(true)
    setError(null)
    try {
      await api.disconnectGog()
      setSettings(await api.settings())
      flash(t('settings.integrations.gogNotConnected'))
    } catch (gogError) {
      reportError(gogError)
    } finally {
      setGogBusy(false)
    }
  }

  const connectEpic = async () => {
    if (!epicCode.trim()) {
      setError(t('settings.integrations.epicCodeHint'))
      return
    }
    setEpicBusy(true)
    setError(null)
    try {
      const result = await api.connectEpic(epicCode.trim())
      setEpicCode('')
      setSettings(await api.settings())
      flash(
        result.message ??
          t('settings.integrations.epicSynced', {
            games: result.games_synced ?? 0,
          }),
      )
    } catch (epicError) {
      reportError(epicError)
    } finally {
      setEpicBusy(false)
    }
  }

  const syncEpicNow = async () => {
    setEpicBusy(true)
    setError(null)
    try {
      const result = await api.syncEpic()
      setSettings(await api.settings())
      flash(
        result.message ??
          t('settings.integrations.epicSynced', {
            games: result.games_synced ?? 0,
          }),
      )
    } catch (epicError) {
      reportError(epicError)
    } finally {
      setEpicBusy(false)
    }
  }

  const disconnectEpic = async () => {
    if (!window.confirm(t('settings.integrations.epicDisconnectConfirm'))) return
    setEpicBusy(true)
    setError(null)
    try {
      await api.disconnectEpic()
      setSettings(await api.settings())
      flash(t('settings.integrations.epicNotConnected'))
    } catch (epicError) {
      reportError(epicError)
    } finally {
      setEpicBusy(false)
    }
  }

  const clearMetadataKey = async (
    field: 'mobygames_api_key' | 'opencritic_api_key',
  ) => {
    if (!window.confirm(t('settings.integrations.confirmDelete'))) return
    setSaving(true)
    setError(null)
    try {
      const next = await api.updateSettings({ [field]: '' })
      setSettings(next)
      flash(t('settings.integrations.secretDeleted'))
    } catch (metadataError) {
      reportError(metadataError)
    } finally {
      setSaving(false)
    }
  }

  const syncMetadataNow = async () => {
    setMetadataBusy(true)
    setError(null)
    try {
      const result = await api.syncMetadata()
      setSettings(await api.settings())
      if (result.skipped) {
        flash(result.reason ?? t('settings.integrations.metadataSkipped'))
      } else {
        const summary = t('settings.integrations.metadataSynced', {
          games: result.games_processed,
          moby: result.mobygames_matched,
          critic: result.opencritic_matched,
          hltb: result.hltb_matched,
        })
        flash(result.message ? `${summary} ${result.message}` : summary)
      }
    } catch (metadataError) {
      reportError(metadataError)
    } finally {
      setMetadataBusy(false)
    }
  }

  useEffect(() => {
    if (!xboxDevice) return
    let stopped = false
    let timer: number
    const poll = async () => {
      if (stopped) return
      try {
        const result = await api.pollXboxDevice()
        if (stopped) return
        if (result.status === 'connected') {
          setXboxDevice(null)
          setSettings(await api.settings())
          flash(result.message ?? t('settings.integrations.xboxConnectedMessage'))
          return
        }
        if (result.status === 'expired' || result.status === 'error') {
          setXboxDevice(null)
          reportError(result.message ?? t('settings.integrations.xboxError'))
          return
        }
      } catch (pollError) {
        if (!stopped) {
          reportError(pollError)
          setXboxDevice(null)
        }
        return
      }
      if (!stopped) {
        timer = window.setTimeout(
          poll,
          Math.max(5, xboxDevice.interval) * 1000,
        )
      }
    }

    timer = window.setTimeout(poll, Math.max(5, xboxDevice.interval) * 1000)
    return () => {
      stopped = true
      window.clearTimeout(timer)
    }
  }, [xboxDevice])

  const createUser = async (event: FormEvent) => {
    event.preventDefault()
    setSaving(true)
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
      flash(t('settings.users.created'))
    } catch (createError) {
      reportError(createError)
    } finally {
      setSaving(false)
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
      flash(t('settings.users.updated'))
    } catch (updateError) {
      reportError(updateError)
    }
  }

  const deleteUser = async (user: CurrentUser) => {
    if (!window.confirm(t('settings.users.deleteConfirm', { username: user.username }))) {
      return
    }
    setError(null)
    try {
      await api.deleteUser(user.id)
      setUsers(await api.users())
      flash(t('settings.users.deleted'))
    } catch (deleteError) {
      reportError(deleteError)
    }
  }

  const changeAccountPassword = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    if (accountPassword !== accountConfirm) {
      setError(t('settings.account.mismatch'))
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
      flash(t('settings.account.changed'))
    } catch (passwordError) {
      reportError(passwordError)
    }
  }

  const downloadBackup = async (format: 'json' | 'sqlite') => {
    setBackupBusy(format === 'json' ? 'download-json' : 'download-sqlite')
    setError(null)
    try {
      const { blob, filename } = await api.downloadBackup(format)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = filename
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
    } catch (downloadError) {
      reportError(downloadError)
    } finally {
      setBackupBusy(null)
    }
  }

  const restoreBackup = async (format: 'json' | 'sqlite', file: File | null) => {
    if (!file) {
      setError(t('settings.backup.noFile'))
      return
    }
    if (!window.confirm(t('settings.backup.confirm'))) return
    setBackupBusy(format === 'json' ? 'upload-json' : 'upload-sqlite')
    setError(null)
    try {
      await api.restoreBackup(format, file)
      window.alert(t('settings.backup.restored'))
      window.location.reload()
    } catch (restoreError) {
      reportError(restoreError)
    } finally {
      setBackupBusy(null)
    }
  }

  const tabs: { id: SettingsTab; labelKey: TranslationKey; icon: typeof Users }[] = [
    { id: 'general', labelKey: 'settings.tabs.general', icon: Server },
    { id: 'integrations', labelKey: 'settings.tabs.integrations', icon: Wifi },
    { id: 'users', labelKey: 'settings.tabs.users', icon: Users },
    { id: 'account', labelKey: 'settings.tabs.account', icon: Shield },
    { id: 'backup', labelKey: 'settings.tabs.backup', icon: Database },
    { id: 'docs', labelKey: 'settings.tabs.docs', icon: BookOpen },
  ]

  if (loading) {
    return (
      <div className="loading-state">
        <span className="loading-state__icon">
          <RefreshCw size={22} strokeWidth={2.2} className="is-spinning" />
        </span>
        <span>{t('settings.loading')}</span>
      </div>
    )
  }

  return (
    <div className="settings-page">
      <div className="settings-tabs" role="tablist" aria-label={t('page.settings.title')}>
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
              {t(item.labelKey)}
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
                <h2>{t('settings.general.title')}</h2>
                <p>{t('settings.general.subtitle')}</p>
              </div>
            </header>
            <form className="settings-form" onSubmit={saveGeneral}>
              <label className="field">
                <span>{t('settings.timezone')}</span>
                <input
                  className="input"
                  value={timezone}
                  onChange={(event) => setTimezone(event.target.value)}
                  placeholder="Europe/Paris"
                  required
                />
                <small>{t('settings.timezoneHint')}</small>
              </label>
              <button type="submit" className="button button--primary" disabled={saving}>
                <Save size={15} strokeWidth={2} />
                {t('common.save')}
              </button>
            </form>
          </section>

          <section className="panel settings-panel">
            <header className="card-head">
              <div>
                <h2>{t('settings.agent.title')}</h2>
                <p>{t('settings.agent.subtitle')}</p>
              </div>
              <span
                className={`config-status${settings.agent_api_key_set ? ' is-on' : ' is-off'}`}
              >
                {settings.agent_api_key_set
                  ? t('common.configuredF')
                  : t('common.missingF')}
              </span>
            </header>

            <div className="agent-key">
              <code>{revealedAgentKey ?? settings.agent_api_key_hint ?? '—'}</code>
              <button
                type="button"
                className="button button--icon"
                onClick={revealAgentKey}
                aria-label={
                  revealedAgentKey ? t('settings.agent.hide') : t('settings.agent.reveal')
                }
                title={
                  revealedAgentKey ? t('settings.agent.hide') : t('settings.agent.reveal')
                }
              >
                {revealedAgentKey ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
              <button
                type="button"
                className="button button--icon"
                onClick={copyAgentKey}
                aria-label={t('settings.agent.copy')}
                title={t('settings.agent.copy')}
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
                {t('settings.agent.rotate')}
              </button>
            </div>
            <p className="settings-hint">
              {t('settings.agent.endpoint', {
                url: `${window.location.origin}/api/heartbeat`,
              })}
            </p>
          </section>
        </div>
      )}

      {tab === 'integrations' && settings && (
        <section className="panel settings-panel">
          <header className="card-head">
            <div>
              <h2>{t('settings.integrations.title')}</h2>
              <p>{t('settings.integrations.subtitle')}</p>
            </div>
          </header>

          <form className="settings-form" onSubmit={saveIntegrations}>
            <div className="settings-group">
              <div className="settings-group__head">
                <h3>{t('settings.integrations.steam')}</h3>
                <span
                  className={`config-status${settings.steam_configured ? ' is-on' : ' is-off'}`}
                >
                  {settings.steam_configured
                    ? t('common.configured')
                    : t('common.notConfigured')}
                </span>
              </div>
              <div className="form-grid">
                <label className="field">
                  <span>{t('settings.integrations.steamKey')}</span>
                  <input
                    className="input"
                    type="password"
                    value={steamKey}
                    onChange={(event) => setSteamKey(event.target.value)}
                    placeholder={
                      settings.steam_api_key_set
                        ? settings.steam_api_key_hint
                        : t('settings.integrations.keepSecret')
                    }
                    autoComplete="off"
                  />
                </label>
                <label className="field">
                  <span>{t('settings.integrations.steamId')}</span>
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
                  {t('settings.integrations.deleteSteamKey')}
                </button>
              )}
            </div>

            <div className="settings-group">
              <div className="settings-group__head">
                <h3>{t('settings.integrations.igdb')}</h3>
                <span
                  className={`config-status${settings.igdb_configured ? ' is-on' : ' is-off'}`}
                >
                  {settings.igdb_configured
                    ? t('common.configured')
                    : t('common.notConfigured')}
                </span>
              </div>
              <div className="form-grid">
                <label className="field">
                  <span>{t('settings.integrations.clientId')}</span>
                  <input
                    className="input"
                    value={igdbClientId}
                    onChange={(event) => setIgdbClientId(event.target.value)}
                    autoComplete="off"
                  />
                </label>
                <label className="field">
                  <span>{t('settings.integrations.clientSecret')}</span>
                  <input
                    className="input"
                    type="password"
                    value={igdbSecret}
                    onChange={(event) => setIgdbSecret(event.target.value)}
                    placeholder={
                      settings.igdb_client_secret_set
                        ? settings.igdb_client_secret_hint
                        : t('settings.integrations.keepSecret')
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
                  {t('settings.integrations.deleteIgdbSecret')}
                </button>
              )}
            </div>

            <div className="settings-group">
              <div className="settings-group__head">
                <h3>{t('settings.integrations.homepage')}</h3>
                <span
                  className={`config-status${
                    settings.homepage_api_token_set ? ' is-on' : ' is-off'
                  }`}
                >
                  {settings.homepage_api_token_set
                    ? t('common.configured')
                    : t('settings.integrations.homepageMissing')}
                </span>
              </div>
              <p className="settings-hint">{t('settings.integrations.homepageSubtitle')}</p>
              <div className="agent-key">
                <code>{revealedHomepageToken ?? settings.homepage_api_token_hint ?? '—'}</code>
                <button
                  type="button"
                  className="button button--icon"
                  onClick={revealHomepageToken}
                  disabled={!settings.homepage_api_token_set}
                  aria-label={
                    revealedHomepageToken
                      ? t('settings.integrations.homepageHide')
                      : t('settings.integrations.homepageReveal')
                  }
                  title={
                    revealedHomepageToken
                      ? t('settings.integrations.homepageHide')
                      : t('settings.integrations.homepageReveal')
                  }
                >
                  {revealedHomepageToken ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
                <button
                  type="button"
                  className="button button--icon"
                  onClick={copyHomepageToken}
                  disabled={!settings.homepage_api_token_set}
                  aria-label={t('settings.integrations.homepageCopy')}
                  title={t('settings.integrations.homepageCopy')}
                >
                  <Copy size={15} />
                </button>
              </div>
              <div className="settings-actions">
                <button
                  type="button"
                  className="button"
                  onClick={rotateHomepageToken}
                  disabled={saving}
                >
                  <Globe2 size={14} strokeWidth={2} />
                  {t('settings.integrations.homepageRotate')}
                </button>
              </div>
              <p className="settings-hint">
                {t('settings.integrations.homepageEndpoint', {
                  url: `${window.location.origin}/api/homepage`,
                })}
              </p>
            </div>

            <div className="settings-group">
              <div className="settings-group__head">
                <h3>{t('settings.integrations.influxdb')}</h3>
                <span
                  className={`config-status${
                    settings.influxdb_configured ? ' is-on' : ' is-off'
                  }`}
                >
                  {settings.influxdb_configured
                    ? t('common.configured')
                    : t('common.notConfigured')}
                </span>
              </div>
              <p className="settings-hint">
                {t('settings.integrations.influxdbSubtitle')}
              </p>
              <div className="form-grid">
                <label className="field">
                  <span>{t('settings.integrations.influxUrl')}</span>
                  <input
                    className="input"
                    value={influxUrl}
                    onChange={(event) => setInfluxUrl(event.target.value)}
                    placeholder="http://influxdb:8086"
                    autoComplete="off"
                  />
                </label>
                <label className="field">
                  <span>{t('settings.integrations.influxToken')}</span>
                  <input
                    className="input"
                    type="password"
                    value={influxToken}
                    onChange={(event) => setInfluxToken(event.target.value)}
                    placeholder={
                      settings.influxdb_token_set
                        ? settings.influxdb_token_hint
                        : t('settings.integrations.keepSecret')
                    }
                    autoComplete="off"
                  />
                </label>
                <label className="field">
                  <span>{t('settings.integrations.influxOrg')}</span>
                  <input
                    className="input"
                    value={influxOrg}
                    onChange={(event) => setInfluxOrg(event.target.value)}
                    autoComplete="off"
                  />
                </label>
                <label className="field">
                  <span>{t('settings.integrations.influxBucket')}</span>
                  <input
                    className="input"
                    value={influxBucket}
                    onChange={(event) => setInfluxBucket(event.target.value)}
                    autoComplete="off"
                  />
                </label>
              </div>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={influxEnabled}
                  onChange={(event) => setInfluxEnabled(event.target.checked)}
                />
                <span>{t('settings.integrations.influxEnabled')}</span>
              </label>
              <div className="settings-actions">
                <button
                  type="button"
                  className="button"
                  onClick={exportInfluxNow}
                  disabled={influxBusy || !settings.influxdb_configured}
                >
                  <RefreshCw
                    size={14}
                    strokeWidth={2}
                    className={influxBusy ? 'is-spinning' : undefined}
                  />
                  {t('settings.integrations.influxExportNow')}
                </button>
                <span className="settings-hint inline-hint">
                  {t('settings.integrations.influxLastExport')} :{' '}
                  {settings.influxdb_last_export_at
                    ? formatRelative(settings.influxdb_last_export_at, lang)
                    : t('common.never')}
                </span>
              </div>
            </div>

            <div className="settings-group">
              <div className="settings-group__head">
                <h3>{t('settings.integrations.xbox')}</h3>
                <span
                  className={`config-status${
                    settings.xbox_connected ? ' is-on' : ' is-off'
                  }`}
                >
                  {settings.xbox_connected
                    ? t('settings.integrations.xboxConnected')
                    : t('settings.integrations.xboxNotConnected')}
                </span>
              </div>
              <p className="settings-hint">{t('settings.integrations.xboxSubtitle')}</p>

              <label className="field">
                <span>{t('settings.integrations.xboxClientId')}</span>
                <input
                  className="input"
                  value={xboxClientId}
                  onChange={(event) => setXboxClientId(event.target.value)}
                  autoComplete="off"
                  spellCheck={false}
                />
                <small>{t('settings.integrations.xboxClientIdHint')}</small>
              </label>

              {settings.xbox_connected ? (
                <div className="xbox-connected">
                  <div className="xbox-metrics">
                    <span>
                      {t('settings.integrations.xboxGamerscore')}
                      <strong>{settings.xbox_gamerscore}</strong>
                    </span>
                    {settings.xbox_gamertag && (
                      <span>
                        Gamertag
                        <strong>{settings.xbox_gamertag}</strong>
                      </span>
                    )}
                    <span>
                      {t('settings.integrations.xboxLastSync')}
                      <strong>
                        {settings.xbox_last_sync_at
                          ? formatRelative(settings.xbox_last_sync_at, lang)
                          : t('common.never')}
                      </strong>
                    </span>
                  </div>
                  <div className="settings-actions">
                    <button
                      type="button"
                      className="button"
                      onClick={syncXboxNow}
                      disabled={xboxBusy}
                    >
                      <RefreshCw
                        size={14}
                        strokeWidth={2}
                        className={xboxBusy ? 'is-spinning' : undefined}
                      />
                      {t('settings.integrations.xboxSync')}
                    </button>
                    <button
                      type="button"
                      className="button button--danger"
                      onClick={disconnectXbox}
                      disabled={xboxBusy}
                    >
                      {t('settings.integrations.xboxDisconnect')}
                    </button>
                  </div>
                </div>
              ) : xboxDevice ? (
                <div className="xbox-device">
                  <span>
                    {t('settings.integrations.xboxCodeHint', {
                      url: xboxDevice.verification_uri,
                    })}
                  </span>
                  <strong>{xboxDevice.user_code}</strong>
                  <a
                    href={xboxDevice.verification_uri}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {xboxDevice.verification_uri}
                    <ExternalLink size={12} />
                  </a>
                  <small>{t('settings.integrations.xboxWaiting')}</small>
                </div>
              ) : (
                <div className="settings-actions">
                  <button
                    type="button"
                    className="button"
                    onClick={startXboxConnection}
                    disabled={xboxBusy || !settings.xbox_client_id}
                  >
                    <Globe2 size={14} strokeWidth={2} />
                    {t('settings.integrations.xboxConnect')}
                  </button>
                </div>
              )}
            </div>

            <div className="settings-group">
              <div className="settings-group__head">
                <h3>{t('settings.integrations.ubisoft')}</h3>
                <span
                  className={`config-status${
                    settings.ubisoft_connected ? ' is-on' : ' is-off'
                  }`}
                >
                  {settings.ubisoft_connected
                    ? t('settings.integrations.ubisoftConnected')
                    : t('settings.integrations.ubisoftNotConnected')}
                </span>
              </div>
              <p className="settings-hint">
                {t('settings.integrations.ubisoftSubtitle')}
              </p>

              <label className="field">
                <span>{t('settings.integrations.ubisoftTicket')}</span>
                <input
                  className="input"
                  type="password"
                  value={ubisoftTicket}
                  onChange={(event) => setUbisoftTicket(event.target.value)}
                  placeholder={
                    settings.ubisoft_remember_me_ticket_set
                      ? settings.ubisoft_remember_me_ticket_hint
                      : t('settings.integrations.ubisoftTicket')
                  }
                  autoComplete="off"
                />
                <small>{t('settings.integrations.ubisoftTicketHint')}</small>
              </label>

              {settings.ubisoft_connected && (
                <div className="xbox-metrics">
                  {settings.ubisoft_name && (
                    <span>
                      Ubisoft
                      <strong>{settings.ubisoft_name}</strong>
                    </span>
                  )}
                  <span>
                    {t('settings.integrations.ubisoftLastSync')}
                    <strong>
                      {settings.ubisoft_last_sync_at
                        ? formatRelative(settings.ubisoft_last_sync_at, lang)
                        : t('common.never')}
                    </strong>
                  </span>
                </div>
              )}

              <div className="settings-actions">
                <button
                  type="button"
                  className="button"
                  onClick={connectUbisoft}
                  disabled={ubisoftBusy || !ubisoftTicket.trim()}
                >
                  <Globe2 size={14} strokeWidth={2} />
                  {t('settings.integrations.ubisoftConnect')}
                </button>
                {settings.ubisoft_connected && (
                  <>
                    <button
                      type="button"
                      className="button"
                      onClick={syncUbisoftNow}
                      disabled={ubisoftBusy}
                    >
                      <RefreshCw
                        size={14}
                        strokeWidth={2}
                        className={ubisoftBusy ? 'is-spinning' : undefined}
                      />
                      {t('settings.integrations.ubisoftSync')}
                    </button>
                    <button
                      type="button"
                      className="button button--danger"
                      onClick={disconnectUbisoft}
                      disabled={ubisoftBusy}
                    >
                      {t('settings.integrations.ubisoftDisconnect')}
                    </button>
                  </>
                )}
              </div>
              <p className="settings-hint">
                {t('settings.integrations.ubisoftNoPlaytime')}
              </p>
            </div>

            <div className="settings-group">
              <div className="settings-group__head">
                <h3>{t('settings.integrations.gog')}</h3>
                <span
                  className={`config-status${
                    settings.gog_connected ? ' is-on' : ' is-off'
                  }`}
                >
                  {settings.gog_connected
                    ? t('settings.integrations.gogConnected')
                    : t('settings.integrations.gogNotConnected')}
                </span>
              </div>
              <p className="settings-hint">
                {t('settings.integrations.gogSubtitle')}
              </p>

              {gogAuthUrl && (
                <div className="settings-actions">
                  <a
                    className="button"
                    href={gogAuthUrl}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <ExternalLink size={14} strokeWidth={2} />
                    {t('settings.integrations.gogOpenAuth')}
                  </a>
                </div>
              )}

              <label className="field">
                <span>{t('settings.integrations.gogCode')}</span>
                <input
                  className="input"
                  type="text"
                  value={gogCode}
                  onChange={(event) => setGogCode(event.target.value)}
                  placeholder="code"
                  autoComplete="off"
                  spellCheck={false}
                />
                <small>{t('settings.integrations.gogCodeHint')}</small>
              </label>

              {settings.gog_connected && (
                <div className="xbox-metrics">
                  {settings.gog_username && (
                    <span>
                      GOG
                      <strong>{settings.gog_username}</strong>
                    </span>
                  )}
                  <span>
                    {t('settings.integrations.gogLastSync')}
                    <strong>
                      {settings.gog_last_sync_at
                        ? formatRelative(settings.gog_last_sync_at, lang)
                        : t('common.never')}
                    </strong>
                  </span>
                </div>
              )}

              <div className="settings-actions">
                <button
                  type="button"
                  className="button"
                  onClick={connectGog}
                  disabled={gogBusy || !gogCode.trim()}
                >
                  <Globe2 size={14} strokeWidth={2} />
                  {t('settings.integrations.gogConnect')}
                </button>
                {settings.gog_connected && (
                  <>
                    <button
                      type="button"
                      className="button"
                      onClick={syncGogNow}
                      disabled={gogBusy}
                    >
                      <RefreshCw
                        size={14}
                        strokeWidth={2}
                        className={gogBusy ? 'is-spinning' : undefined}
                      />
                      {t('settings.integrations.gogSync')}
                    </button>
                    <button
                      type="button"
                      className="button button--danger"
                      onClick={disconnectGog}
                      disabled={gogBusy}
                    >
                      {t('settings.integrations.gogDisconnect')}
                    </button>
                  </>
                )}
              </div>
              <p className="settings-hint">
                {t('settings.integrations.gogNoPlaytime')}
              </p>
            </div>

            <div className="settings-group">
              <div className="settings-group__head">
                <h3>{t('settings.integrations.epic')}</h3>
                <span
                  className={`config-status${
                    settings.epic_connected ? ' is-on' : ' is-off'
                  }`}
                >
                  {settings.epic_connected
                    ? t('settings.integrations.epicConnected')
                    : t('settings.integrations.epicNotConnected')}
                </span>
              </div>
              <p className="settings-hint">
                {t('settings.integrations.epicSubtitle')}
              </p>

              {epicAuthUrl && (
                <div className="settings-actions">
                  <a
                    className="button"
                    href={epicAuthUrl}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <ExternalLink size={14} strokeWidth={2} />
                    {t('settings.integrations.epicOpenAuth')}
                  </a>
                </div>
              )}

              <label className="field">
                <span>{t('settings.integrations.epicCode')}</span>
                <textarea
                  className="input"
                  value={epicCode}
                  onChange={(event) => setEpicCode(event.target.value)}
                  placeholder='{"authorizationCode":"..."}'
                  rows={2}
                  autoComplete="off"
                  spellCheck={false}
                />
                <small>{t('settings.integrations.epicCodeHint')}</small>
              </label>

              {settings.epic_connected && (
                <div className="xbox-metrics">
                  {settings.epic_display_name && (
                    <span>
                      Epic
                      <strong>{settings.epic_display_name}</strong>
                    </span>
                  )}
                  <span>
                    {t('settings.integrations.epicLastSync')}
                    <strong>
                      {settings.epic_last_sync_at
                        ? formatRelative(settings.epic_last_sync_at, lang)
                        : t('common.never')}
                    </strong>
                  </span>
                </div>
              )}

              <div className="settings-actions">
                <button
                  type="button"
                  className="button"
                  onClick={connectEpic}
                  disabled={epicBusy || !epicCode.trim()}
                >
                  <Globe2 size={14} strokeWidth={2} />
                  {t('settings.integrations.epicConnect')}
                </button>
                {settings.epic_connected && (
                  <>
                    <button
                      type="button"
                      className="button"
                      onClick={syncEpicNow}
                      disabled={epicBusy}
                    >
                      <RefreshCw
                        size={14}
                        strokeWidth={2}
                        className={epicBusy ? 'is-spinning' : undefined}
                      />
                      {t('settings.integrations.epicSync')}
                    </button>
                    <button
                      type="button"
                      className="button button--danger"
                      onClick={disconnectEpic}
                      disabled={epicBusy}
                    >
                      {t('settings.integrations.epicDisconnect')}
                    </button>
                  </>
                )}
              </div>
              <p className="settings-hint">
                {t('settings.integrations.epicNoPlaytime')}{' '}
                {t('settings.integrations.epicPartialAchievements')}
              </p>
            </div>

            <div className="settings-group">
              <div className="settings-group__head">
                <h3>{t('settings.integrations.metadata')}</h3>
              </div>
              <p className="settings-hint">
                {t('settings.integrations.metadataSubtitle')}
              </p>
              <p className="settings-hint">
                {t('settings.integrations.metadataStatus', {
                  moby: settings.mobygames_configured
                    ? t('common.configured')
                    : t('common.notConfigured'),
                  critic: settings.opencritic_configured
                    ? t('common.configured')
                    : t('common.notConfigured'),
                  hltb: settings.hltb_enabled
                    ? t('common.active')
                    : t('common.disabled'),
                })}
              </p>

              <label className="field">
                <span>{t('settings.integrations.mobygamesKey')}</span>
                <input
                  className="input"
                  type="password"
                  value={mobygamesKey}
                  onChange={(event) => setMobygamesKey(event.target.value)}
                  placeholder={
                    settings.mobygames_api_key_set
                      ? settings.mobygames_api_key_hint
                      : t('settings.integrations.mobygamesKey')
                  }
                  autoComplete="off"
                />
                <small>
                  {t('settings.integrations.mobygamesHint')}{' '}
                  <a
                    href="https://www.mobygames.com/info/api/"
                    target="_blank"
                    rel="noreferrer"
                  >
                    {t('settings.integrations.mobygamesOpen')}
                  </a>
                </small>
              </label>
              {settings.mobygames_api_key_set && (
                <div className="settings-actions">
                  <button
                    type="button"
                    className="button button--danger"
                    onClick={() => clearMetadataKey('mobygames_api_key')}
                    disabled={saving}
                  >
                    <Trash2 size={14} strokeWidth={2} />
                    {t('settings.integrations.deleteKey')}
                  </button>
                </div>
              )}

              <label className="field">
                <span>{t('settings.integrations.opencriticKey')}</span>
                <input
                  className="input"
                  type="password"
                  value={opencriticKey}
                  onChange={(event) => setOpencriticKey(event.target.value)}
                  placeholder={
                    settings.opencritic_api_key_set
                      ? settings.opencritic_api_key_hint
                      : t('settings.integrations.opencriticKey')
                  }
                  autoComplete="off"
                />
                <small>
                  {t('settings.integrations.opencriticHint')}{' '}
                  <a
                    href="https://rapidapi.com/opencritic-opencritic-default/api/opencritic-api"
                    target="_blank"
                    rel="noreferrer"
                  >
                    {t('settings.integrations.opencriticOpen')}
                  </a>
                </small>
              </label>
              {settings.opencritic_api_key_set && (
                <div className="settings-actions">
                  <button
                    type="button"
                    className="button button--danger"
                    onClick={() => clearMetadataKey('opencritic_api_key')}
                    disabled={saving}
                  >
                    <Trash2 size={14} strokeWidth={2} />
                    {t('settings.integrations.deleteKey')}
                  </button>
                </div>
              )}

              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={hltbEnabled}
                  onChange={(event) => setHltbEnabled(event.target.checked)}
                />
                <span>{t('settings.integrations.hltbEnabled')}</span>
              </label>
              <p className="settings-hint">
                {t('settings.integrations.hltbHint')}
              </p>

              <div className="settings-actions">
                <button
                  type="button"
                  className="button"
                  onClick={syncMetadataNow}
                  disabled={
                    metadataBusy ||
                    (!settings.mobygames_configured &&
                      !settings.opencritic_configured &&
                      !settings.hltb_enabled)
                  }
                >
                  <RefreshCw
                    size={14}
                    strokeWidth={2}
                    className={metadataBusy ? 'is-spinning' : undefined}
                  />
                  {t('settings.integrations.metadataSync')}
                </button>
                <span className="settings-hint inline-hint">
                  {t('settings.integrations.metadataLastSync')} :{' '}
                  {settings.metadata_last_sync_at
                    ? formatRelative(settings.metadata_last_sync_at, lang)
                    : t('common.never')}
                </span>
              </div>
              <p className="settings-hint">
                {t('settings.integrations.metadataGiantBomb')}
              </p>
            </div>

            <button type="submit" className="button button--primary" disabled={saving}>
              <Save size={15} strokeWidth={2} />
              {t('settings.integrations.save')}
            </button>
          </form>
        </section>
      )}

      {tab === 'users' && (
        <div className="settings-stack">
          <section className="panel settings-panel">
            <header className="card-head">
              <div>
                <h2>{t('settings.users.addTitle')}</h2>
                <p>{t('settings.users.addSubtitle')}</p>
              </div>
            </header>
            <form className="user-create-form" onSubmit={createUser}>
              <label className="field">
                <span>{t('settings.users.username')}</span>
                <input
                  className="input"
                  value={newUsername}
                  onChange={(event) => setNewUsername(event.target.value)}
                  required
                  minLength={3}
                />
              </label>
              <label className="field">
                <span>{t('settings.users.email')}</span>
                <input
                  className="input"
                  type="email"
                  value={newEmail}
                  onChange={(event) => setNewEmail(event.target.value)}
                />
              </label>
              <label className="field">
                <span>{t('settings.users.password')}</span>
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
                <span>{t('settings.users.role')}</span>
                <select
                  className="select"
                  value={newRole}
                  onChange={(event) => setNewRole(event.target.value as UserRole)}
                >
                  <option value="viewer">{t('common.viewer')}</option>
                  <option value="admin">{t('common.adminShort')}</option>
                </select>
              </label>
              <button type="submit" className="button button--primary" disabled={saving}>
                <UserPlus size={15} strokeWidth={2} />
                {t('settings.users.create')}
              </button>
            </form>
          </section>

          <section className="panel settings-panel">
            <header className="card-head">
              <div>
                <h2>{t('settings.users.accounts')}</h2>
                <p>{t('settings.users.count', { count: users.length })}</p>
              </div>
            </header>

            <div className="users-table">
              <div className="users-table__head">
                <span>{t('settings.users.user')}</span>
                <span>{t('settings.users.role')}</span>
                <span>{t('settings.users.status')}</span>
                <span>{t('settings.users.lastLogin')}</span>
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
                          <strong>
                            {user.username}
                            {self ? ` ${t('settings.users.you')}` : ''}
                          </strong>
                          <span>{user.email || t('settings.users.noEmail')}</span>
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
                        <option value="viewer">{t('common.viewer')}</option>
                        <option value="admin">{t('common.adminShort')}</option>
                      </select>
                      <span
                        className={`config-status${user.is_active ? ' is-on' : ' is-off'}`}
                      >
                        {user.is_active ? t('common.active') : t('common.disabled')}
                      </span>
                      <span className="user-last-login">
                        {user.last_login_at
                          ? formatRelative(user.last_login_at, lang)
                          : t('common.never')}
                      </span>
                      <div className="user-actions">
                        <button
                          type="button"
                          className="button button--icon"
                          title={
                            user.is_active
                              ? t('settings.users.deactivate')
                              : t('settings.users.activate')
                          }
                          aria-label={
                            user.is_active
                              ? t('settings.users.deactivate')
                              : t('settings.users.activate')
                          }
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
                          title={t('settings.users.resetPassword')}
                          aria-label={t('settings.users.resetPassword')}
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
                          title={t('common.delete')}
                          aria-label={t('common.delete')}
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
                          placeholder={t('settings.users.newPasswordPlaceholder')}
                          minLength={8}
                          required
                        />
                        <button type="submit" className="button button--primary">
                          {t('common.apply')}
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
              <h2>{t('settings.account.title')}</h2>
              <p>{t('settings.account.subtitle', { username: currentUser.username })}</p>
            </div>
          </header>
          <form className="settings-form" onSubmit={changeAccountPassword}>
            <label className="field">
              <span>{t('settings.account.currentPassword')}</span>
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
                <span>{t('settings.account.newPassword')}</span>
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
                <span>{t('settings.account.confirm')}</span>
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
              {t('settings.account.change')}
            </button>
          </form>
        </section>
      )}

      {tab === 'backup' && (
        <section className="panel settings-panel">
          <header className="card-head">
            <div>
              <h2>{t('settings.backup.title')}</h2>
              <p>{t('settings.backup.subtitle')}</p>
            </div>
          </header>

          <div className="backup-warning">
            <AlertTriangle size={16} strokeWidth={2} />
            {t('settings.backup.warning')}
          </div>

          <div className="backup-grid">
            <div className="backup-card">
              <div>
                <h3>{t('settings.backup.exportTitle')}</h3>
                <p>{t('settings.backup.exportText')}</p>
              </div>
              <div className="backup-actions">
                <button
                  type="button"
                  className="button"
                  onClick={() => downloadBackup('json')}
                  disabled={backupBusy !== null}
                >
                  <Download size={14} strokeWidth={2} />
                  {backupBusy === 'download-json'
                    ? t('settings.backup.downloading')
                    : t('settings.backup.downloadJson')}
                </button>
                <button
                  type="button"
                  className="button"
                  onClick={() => downloadBackup('sqlite')}
                  disabled={backupBusy !== null}
                >
                  <Download size={14} strokeWidth={2} />
                  {backupBusy === 'download-sqlite'
                    ? t('settings.backup.downloading')
                    : t('settings.backup.downloadSqlite')}
                </button>
              </div>
            </div>

            <div className="backup-card">
              <div>
                <h3>{t('settings.backup.restoreTitle')}</h3>
                <p>{t('settings.backup.restoreText')}</p>
              </div>
              <div className="backup-actions">
                <button
                  type="button"
                  className="button"
                  onClick={() => jsonInputRef.current?.click()}
                  disabled={backupBusy !== null}
                >
                  <Upload size={14} strokeWidth={2} />
                  {backupBusy === 'upload-json'
                    ? t('settings.backup.uploading')
                    : t('settings.backup.restoreJson')}
                </button>
                <input
                  ref={jsonInputRef}
                  className="file-input"
                  type="file"
                  accept=".json,application/json"
                  onChange={(event) => {
                    void restoreBackup('json', event.target.files?.[0] ?? null)
                    event.target.value = ''
                  }}
                />
                <button
                  type="button"
                  className="button"
                  onClick={() => sqliteInputRef.current?.click()}
                  disabled={backupBusy !== null}
                >
                  <Upload size={14} strokeWidth={2} />
                  {backupBusy === 'upload-sqlite'
                    ? t('settings.backup.uploading')
                    : t('settings.backup.restoreSqlite')}
                </button>
                <input
                  ref={sqliteInputRef}
                  className="file-input"
                  type="file"
                  accept=".db,.sqlite,application/vnd.sqlite3"
                  onChange={(event) => {
                    void restoreBackup('sqlite', event.target.files?.[0] ?? null)
                    event.target.value = ''
                  }}
                />
              </div>
            </div>
          </div>
        </section>
      )}

      {tab === 'docs' && (
        <div className="settings-stack">
          <section className="panel settings-panel">
            <header className="card-head">
              <div>
                <h2>{t('settings.docs.title')}</h2>
                <p>{t('settings.docs.subtitle')}</p>
              </div>
            </header>
            <div className="docs-links">
              <a href={docsLinks.swagger} target="_blank" rel="noreferrer">
                <BookOpen size={17} strokeWidth={2} />
                <span>
                  <strong>{t('settings.docs.swagger')}</strong>
                  <small>{t('settings.docs.swaggerHint')}</small>
                </span>
                <ExternalLink size={14} />
              </a>
              <a href={docsLinks.redoc} target="_blank" rel="noreferrer">
                <BookOpen size={17} strokeWidth={2} />
                <span>
                  <strong>{t('settings.docs.redoc')}</strong>
                  <small>{t('settings.docs.redocHint')}</small>
                </span>
                <ExternalLink size={14} />
              </a>
              <a href={docsLinks.readme} target="_blank" rel="noreferrer">
                <BookOpen size={17} strokeWidth={2} />
                <span>
                  <strong>{t('settings.docs.readme')}</strong>
                  <small>{t('settings.docs.readmeHint')}</small>
                </span>
                <ExternalLink size={14} />
              </a>
            </div>
          </section>

          <section className="panel settings-panel">
            <header className="card-head">
              <div>
                <h2>{t('settings.docs.agentTitle')}</h2>
                <p>{t('settings.docs.agentSubtitle')}</p>
              </div>
            </header>
            <div className="docs-code">
              <code>POST {window.location.origin}/api/heartbeat</code>
              <code>Header X-Agent-Key: &lt;agent key&gt;</code>
            </div>
            <p className="settings-hint">{t('settings.docs.agentKeyHint')}</p>
          </section>

          <section className="panel settings-panel">
            <header className="card-head">
              <div>
                <h2>{t('settings.docs.homepageTitle')}</h2>
                <p>{t('settings.docs.homepageSubtitle')}</p>
              </div>
            </header>
            <div className="docs-code">
              <pre><code>{`widget:
  type: customapi
  url: ${window.location.origin}/api/homepage
  refreshInterval: 60000
  headers:
    X-API-Key: <homepage-token>
  mappings:
    - field: active_games
      label: In game
    - field: week
      label: This week
    - field: today
      label: Today`}</code></pre>
            </div>
          </section>

          <section className="panel settings-panel">
            <header className="card-head">
              <div>
                <h2>{t('settings.docs.influxTitle')}</h2>
                <p>{t('settings.docs.influxSubtitle')}</p>
              </div>
            </header>
            <div className="docs-code">
              <code>gamestats_session: game, source, game_id, duration_seconds</code>
              <code>gamestats_summary: today_seconds, week_seconds, total_seconds, sessions_week, active_sessions, library_count, agents_online</code>
            </div>
            <p className="settings-hint">
              {t('settings.docs.influxHint')}
            </p>
          </section>

          <section className="panel settings-panel">
            <header className="card-head">
              <div>
                <h2>{t('settings.docs.xboxTitle')}</h2>
                <p>{t('settings.docs.xboxSubtitle')}</p>
              </div>
            </header>
            <div className="docs-code">
              <code>Azure app registration → Allow public client flows: Yes</code>
              <code>Scopes: XboxLive.signin XboxLive.offline_access</code>
              <code>Connect from Settings → Integrations → Xbox</code>
            </div>
            <p className="settings-hint">{t('settings.docs.xboxHint')}</p>
          </section>

          <section className="panel settings-panel">
            <header className="card-head">
              <div>
                <h2>{t('settings.docs.ubisoftTitle')}</h2>
                <p>{t('settings.docs.ubisoftSubtitle')}</p>
              </div>
            </header>
            <div className="docs-code">
              <code>rememberMeTicket → Settings → Integrations → Ubisoft</code>
              <code>GET /v1/profiles/gamesplayed?profileIds=...</code>
            </div>
            <p className="settings-hint">{t('settings.docs.ubisoftHint')}</p>
          </section>

          <section className="panel settings-panel">
            <header className="card-head">
              <div>
                <h2>{t('settings.docs.gogTitle')}</h2>
                <p>{t('settings.docs.gogSubtitle')}</p>
              </div>
            </header>
            <div className="docs-code">
              <code>auth.gog.com/auth → redirect code → Settings → Integrations → GOG</code>
              <code>GET /user/data/games · gameplay.gog.com achievements</code>
            </div>
            <p className="settings-hint">{t('settings.docs.gogHint')}</p>
          </section>

          <section className="panel settings-panel">
            <header className="card-head">
              <div>
                <h2>{t('settings.docs.epicTitle')}</h2>
                <p>{t('settings.docs.epicSubtitle')}</p>
              </div>
            </header>
            <div className="docs-code">
              <code>epicgames.com/id/login → authorizationCode → Settings → Integrations → Epic</code>
              <code>library-service .../items · launcher.store.epicgames.com/graphql</code>
            </div>
            <p className="settings-hint">{t('settings.docs.epicHint')}</p>
          </section>

          <section className="panel settings-panel">
            <header className="card-head">
              <div>
                <h2>{t('settings.docs.metadataTitle')}</h2>
                <p>{t('settings.docs.metadataSubtitle')}</p>
              </div>
            </header>
            <div className="docs-code">
              <code>MobyGames → api.mobygames.com/v1/games</code>
              <code>OpenCritic → opencritic-api.p.rapidapi.com/game/search</code>
              <code>HowLongToBeat → howlongtobeat.com/api/search/site</code>
            </div>
            <p className="settings-hint">{t('settings.docs.metadataHint')}</p>
          </section>
        </div>
      )}
    </div>
  )
}
