import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Calendar, BookOpen, Loader2, Check, ExternalLink, RefreshCw, Link2, Unlink, User, Bell, Volume2, Globe } from 'lucide-react'
import { api, pollJob } from '../lib/api'

const TIMEZONES = [
  'America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles',
  'America/Phoenix', 'Europe/London', 'Europe/Berlin', 'Asia/Tokyo', 'Asia/Kolkata',
  'Australia/Sydney', 'Pacific/Auckland', 'UTC',
]

const PHASE_OPTIONS = [
  { value: 'student', label: 'Student' },
  { value: 'early_career', label: 'Early Career' },
  { value: 'mid_career', label: 'Mid Career' },
  { value: 'career_change', label: 'Career Change' },
  { value: 'other', label: 'Other' },
]

const PLANNING_MODES = [
  { value: 'relaxed', label: 'Relaxed', desc: 'More breaks, lighter schedule' },
  { value: 'balanced', label: 'Balanced', desc: 'Mix of productivity and rest' },
  { value: 'focused', label: 'Focused', desc: 'Maximum productivity, fewer breaks' },
]

export default function SettingsPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [calendars, setCalendars] = useState([])
  const [selectedCalendars, setSelectedCalendars] = useState([])
  const [calendarError, setCalendarError] = useState('')
  const [profile, setProfile] = useState(null)
  const [integrations, setIntegrations] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [syncing, setSyncing] = useState(null)
  const [syncResult, setSyncResult] = useState(null)
  const [error, setError] = useState('')
  const [syncStage, setSyncStage] = useState('')

  useEffect(() => {
    async function load() {
      try {
        const [profileData, intData] = await Promise.all([
          api.get('/api/profile'),
          api.get('/api/integrations'),
        ])
        setProfile(profileData.profile || {})
        setIntegrations(intData.integrations || [])
      } catch (err) {
        setError(err.message)
        setProfile({})
      }
      setLoading(false)
    }
    load()
  }, [])

  useEffect(() => {
    if (!integrations.some(i => i.provider === 'google_calendar' && i.status === 'connected')) return
    api.get('/api/integrations/google_calendar/calendars').then(data => { setCalendars(data.calendars); setSelectedCalendars(data.selected); setCalendarError('') }).catch(e => setCalendarError(e.message))
  }, [integrations])
  useEffect(() => {
    if (!loading && window.location.hash) document.getElementById(window.location.hash.slice(1))?.scrollIntoView({block:'center', behavior:'smooth'})
  }, [loading, location.hash])

  const saveCalendars = async () => {
    setError(''); setSyncing('google_calendar')
    try { await api.put('/api/integrations/google_calendar/calendars', {calendar_ids:selectedCalendars}); await syncIntegration('google_calendar'); window.dispatchEvent(new Event('vida:changed')) }
    catch(e) { setError(e.message); setSyncing(null) }
  }
  const saveProfile = async () => {
    setSaving(true)
    try {
      await api.put('/api/profile', profile)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) { setError(err.message) }
    setSaving(false)
  }

  const connectGoogle = async () => {
    try {
      const data = await api.get('/api/auth/google')
      if (data.url) window.location.href = data.url
    } catch (err) { setError(err.message) }
  }

  const connectNotion = async () => {
    try {
      const data = await api.get('/api/auth/notion')
      if (data.url) window.location.href = data.url
    } catch (err) { setError(err.message) }
  }

  useEffect(() => {
    if (!integrations.some(i => i.provider === 'notion' && ['pending','syncing'].includes(i.mirror_status))) return
    const timer = setInterval(async () => {
      try { const data = await api.get('/api/integrations'); setIntegrations(data.integrations || []) } catch { /* Keep the last status; manual Sync remains available. */ }
    }, 5000)
    return () => clearInterval(timer)
  }, [integrations])

  const syncIntegration = async (provider) => {
    setSyncing(provider)
    setSyncResult(null)
    setError('')
    setSyncStage('Importing your latest information…')
    try {
      const { job_id } = await api.post(`/api/integrations/${provider}/sync`)
      const job = await pollJob(job_id)
      const result = job.result || {}
      let replanned = 0
      for (const date of result.replan_dates || []) {
        setSyncStage(`Preparing a plan draft for ${date}…`)
        try {
          const draft = await api.post('/api/plan/replan', { date, reason: 'Calendar availability changed after synchronization' })
          await pollJob(draft.job_id)
          replanned++
        } catch {
          setError('Your calendar was imported, but a plan draft could not be updated. Open Plan to regenerate it.')
        }
      }
      window.dispatchEvent(new Event('vida:changed'))
      const data = await api.get('/api/integrations')
      setIntegrations(data.integrations || [])
      setSyncResult({ provider, synced: result.synced_events ?? result.synced_pages ?? 0, replanned, partial: !!result.partial })
    } catch (err) { setError(err.message) }
    setSyncStage('')
    setSyncing(null)
  }

  const disconnectIntegration = async (provider) => {
    try {
      await api.del(`/api/integrations/${provider}`)
      setIntegrations(prev => prev.filter(i => i.provider !== provider))
      window.dispatchEvent(new Event('vida:changed'))
    } catch (err) { setError(err.message) }
  }

  const isConnected = (provider) => integrations.some(i => i.provider === provider && i.status === 'connected')
  const getIntegration = (provider) => integrations.find(i => i.provider === provider)

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <Loader2 size={32} className="animate-spin text-vida-600" />
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-sm text-gray-500 mt-1">Manage your profile, integrations, and preferences</p>
      </div>

      {error && <div role="alert" className="bg-red-50 text-red-800 rounded-xl p-4">{error}</div>}
      {syncStage && <p role="status" className="text-sm text-gray-600">{syncStage}</p>}
      {syncResult && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4 flex items-center justify-between">
          <div className="text-sm text-green-800">
            <span className="font-medium">Synced {syncResult.synced} {syncResult.provider === 'google_calendar' ? 'calendar events' : 'pages'}</span>
            {syncResult.replanned > 0 && ' — new plan drafts are ready for review'}
            {syncResult.partial && ' — more pages remain. Select Sync again to continue.'}
          </div>
          {syncResult.replanned > 0 && (
            <button onClick={() => navigate('/plan')}
              className="text-sm font-medium text-green-700 hover:text-green-900 underline">
              View Plan
            </button>
          )}
        </div>
      )}

      <span id="integrations" />
      {/* Integrations */}
      <section className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <Link2 size={20} className="text-vida-600" />
            Connected Integrations
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">Google Calendar is required for planning. Choose the calendars to import for the next 7 days and the Notion pages you share. Imported notes are stored in Vida; relevant passages are sent to its AI when you ask a question.</p>
        </div>
        <div className="p-6 space-y-4">
          {/* Google Calendar */}
          <div className="flex items-center justify-between p-4 rounded-xl border border-gray-200 hover:border-gray-300 transition-colors">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center flex-shrink-0">
                <Calendar size={24} className="text-blue-600" />
              </div>
              <div>
                <div id="google-calendar" className="text-sm font-semibold text-gray-900">Google Calendar</div>
                <div className="text-xs text-gray-500">
                  {isConnected('google_calendar')
                    ? `Connected${getIntegration('google_calendar')?.last_synced_at ? ` · Last synced ${new Date(getIntegration('google_calendar').last_synced_at).toLocaleString()}` : ''}`
                    : 'Import events, deadlines, and meetings'}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {isConnected('google_calendar') ? (
                <>
                  <button onClick={() => syncIntegration('google_calendar')} disabled={!!syncing}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-vida-700 bg-vida-50 rounded-lg hover:bg-vida-100 transition-colors disabled:opacity-50">
                    {syncing === 'google_calendar' ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
                    Sync
                  </button>
                  <button onClick={() => disconnectIntegration('google_calendar')}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 rounded-lg transition-colors">
                    <Unlink size={13} /> Disconnect
                  </button>
                </>
              ) : (
                <button onClick={connectGoogle}
                  className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors">
                  <ExternalLink size={14} /> Connect
                </button>
              )}
            </div>
          </div>

          {isConnected('google_calendar') && <div className="rounded-xl border p-4 space-y-3"><h3 className="font-semibold text-sm">Choose calendars to plan around</h3>{calendarError && <div role="alert" className="text-sm text-red-700">{calendarError} <button className="underline" onClick={connectGoogle}>Reconnect Google</button></div>}{calendars.map(c => <label key={c.id} className="flex gap-2 text-sm"><input type="checkbox" checked={selectedCalendars.includes(c.id)} onChange={e => setSelectedCalendars(v => e.target.checked ? [...v,c.id] : v.filter(id => id !== c.id))}/>{c.title}{c.primary ? ' (primary)' : ''}</label>)}<button disabled={!!syncing || !selectedCalendars.length} onClick={saveCalendars} className="px-4 py-2 bg-vida-600 text-white rounded-lg disabled:opacity-50 text-sm">Save selection & sync</button><button className="ml-3 text-sm underline" onClick={() => navigate('/plan')}>Continue to Plan</button></div>}
          {/* Notion */}
          <div className="flex items-center justify-between p-4 rounded-xl border border-gray-200 hover:border-gray-300 transition-colors">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-gray-100 flex items-center justify-center flex-shrink-0">
                <BookOpen size={24} className="text-gray-800" />
              </div>
              <div>
                <div id="notion" className="text-sm font-semibold text-gray-900">Notion</div>
                <div className="text-xs text-gray-500">
                  {isConnected('notion')
                    ? `Connected${getIntegration('notion')?.last_synced_at ? ` · Last synced ${new Date(getIntegration('notion').last_synced_at).toLocaleString()}` : ''}`
                    : 'Connect to create Vida Tasks and Vida Habits and import shared notes'}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {isConnected('notion') ? (
                <>
                  <button onClick={() => syncIntegration('notion')} disabled={!!syncing}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-vida-700 bg-vida-50 rounded-lg hover:bg-vida-100 transition-colors disabled:opacity-50">
                    {syncing === 'notion' ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
                    Sync
                  </button>
                  <button onClick={() => disconnectIntegration('notion')}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 rounded-lg transition-colors">
                    <Unlink size={13} /> Disconnect
                  </button>
                </>
              ) : (
                <button onClick={connectNotion}
                  className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-gray-900 rounded-lg hover:bg-gray-800 transition-colors">
                  <ExternalLink size={14} /> Connect
                </button>
              )}
            </div>
          </div>
        </div>
      </section>

      {isConnected('notion') && <section className="bg-white rounded-xl border p-5 mb-6 space-y-2">
        <h3 className="font-semibold">Your Vida pages in Notion</h3>
        <p className="text-sm text-gray-600">Vida automatically creates Vida Tasks and Vida Habits. Changes in Vida update these pages, including completed tasks and dated habit check-ins. Edit these items in Vida; Notion edits do not sync back. Your other Notion notes stay intact.</p>
        <p role="status" className="text-sm">{getIntegration('notion')?.mirror_status === 'complete' ? `Last updated ${new Date(getIntegration('notion').mirror_synced_at).toLocaleString()}` : getIntegration('notion')?.mirror_status === 'needs_sync' ? 'Needs attention — use Notion Sync above to retry.' : getIntegration('notion')?.mirror_status ? 'Updating your Notion pages…' : 'Use Notion Sync above to create your pages and copy existing tasks and habits.'}</p>
        {getIntegration('notion')?.mirror_error && <p role="alert" className="text-sm text-amber-700">{getIntegration('notion').mirror_error}</p>}
        <div className="flex gap-3">{Object.entries(getIntegration('notion')?.mirror_pages || {}).map(([kind,url]) => <a key={kind} href={url} target="_blank" rel="noopener noreferrer" className="px-3 py-1 border rounded-lg text-sm text-vida-700">Open Vida {kind === 'tasks' ? 'Tasks' : 'Habits'} ↗</a>)}</div>
      </section>}

      {/* Profile */}
      <section className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <User size={20} className="text-vida-600" />
            Profile
          </h2>
        </div>
        <div className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Name</label>
              <input value={profile?.name || ''} onChange={e => setProfile(p => ({ ...p, name: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-vida-500 focus:border-vida-500 outline-none" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Role</label>
              <input value={profile?.role || ''} onChange={e => setProfile(p => ({ ...p, role: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-vida-500 focus:border-vida-500 outline-none" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Life Phase</label>
              <select value={profile?.phase || 'other'} onChange={e => setProfile(p => ({ ...p, phase: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-vida-500 focus:border-vida-500 outline-none bg-white">
                {PHASE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Timezone</label>
              <select value={profile?.timezone || 'America/Los_Angeles'} onChange={e => setProfile(p => ({ ...p, timezone: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-vida-500 focus:border-vida-500 outline-none bg-white">
                {TIMEZONES.map(tz => <option key={tz} value={tz}>{tz.replace(/_/g, ' ')}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Summary</label>
            <textarea value={profile?.summary || ''} onChange={e => setProfile(p => ({ ...p, summary: e.target.value }))} rows={3}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-vida-500 focus:border-vida-500 outline-none resize-none" />
          </div>
          <div className="flex justify-end">
            <button onClick={saveProfile} disabled={saving}
              className="flex items-center gap-2 px-5 py-2 text-sm font-medium text-white bg-vida-600 rounded-lg hover:bg-vida-700 transition-colors disabled:opacity-50">
              {saving ? <Loader2 size={14} className="animate-spin" /> : saved ? <Check size={14} /> : null}
              {saved ? 'Saved!' : 'Save Profile'}
            </button>
          </div>
        </div>
      </section>

      {/* Preferences */}
      <section className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <Bell size={20} className="text-vida-600" />
            Preferences
          </h2>
        </div>
        <div className="p-6 space-y-5">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-2">Planning Mode</label>
            <div className="grid grid-cols-3 gap-3">
              {PLANNING_MODES.map(m => (
                <button key={m.value}
                  onClick={() => setProfile(p => ({ ...p, planning_mode: m.value }))}
                  className={`p-3 rounded-lg border-2 text-left transition-colors ${
                    (profile?.planning_mode || 'balanced') === m.value
                      ? 'border-vida-500 bg-vida-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}>
                  <div className="text-sm font-medium text-gray-800">{m.label}</div>
                  <div className="text-xs text-gray-500 mt-0.5">{m.desc}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between py-2">
            <div>
              <div className="text-sm font-medium text-gray-800 flex items-center gap-2"><Volume2 size={16} /> Voice Responses</div>
              <div className="text-xs text-gray-500">Automatically read AI responses aloud</div>
            </div>
            <button
              onClick={() => {
                const next = !(profile?.voice_auto_read)
                setProfile(p => ({ ...p, voice_auto_read: next }))
              }}
              className={`w-11 h-6 rounded-full transition-colors relative ${
                profile?.voice_auto_read ? 'bg-vida-600' : 'bg-gray-300'
              }`}>
              <span className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                profile?.voice_auto_read ? 'left-[22px]' : 'left-0.5'
              }`} />
            </button>
          </div>

          <div className="flex justify-end pt-2">
            <button onClick={saveProfile} disabled={saving}
              className="flex items-center gap-2 px-5 py-2 text-sm font-medium text-white bg-vida-600 rounded-lg hover:bg-vida-700 transition-colors disabled:opacity-50">
              {saving ? <Loader2 size={14} className="animate-spin" /> : saved ? <Check size={14} /> : null}
              {saved ? 'Saved!' : 'Save Preferences'}
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}
