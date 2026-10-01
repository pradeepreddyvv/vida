import { useState, useEffect } from 'react'
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
  const [profile, setProfile] = useState(null)
  const [integrations, setIntegrations] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [syncing, setSyncing] = useState(null)

  useEffect(() => {
    async function load() {
      try {
        const [profileData, intData] = await Promise.all([
          api.get('/api/profile'),
          api.get('/api/integrations').catch(() => ({ integrations: [] })),
        ])
        setProfile(profileData.profile || {})
        setIntegrations(intData.integrations || [])
      } catch {
        setProfile({})
      }
      setLoading(false)
    }
    load()
  }, [])

  const saveProfile = async () => {
    setSaving(true)
    try {
      await api.put('/api/profile', profile)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch { /* error */ }
    setSaving(false)
  }

  const connectGoogle = () => {
    window.location.href = '/api/auth/google'
  }

  const connectNotion = () => {
    window.location.href = '/api/auth/notion'
  }

  const syncIntegration = async (provider) => {
    setSyncing(provider)
    try {
      const { job_id } = await api.post(`/api/integrations/${provider}/sync`)
      await pollJob(job_id)
      const data = await api.get('/api/integrations').catch(() => ({ integrations: [] }))
      setIntegrations(data.integrations || [])
    } catch { /* error */ }
    setSyncing(null)
  }

  const disconnectIntegration = async (provider) => {
    try {
      await api.del(`/api/integrations/${provider}`)
      setIntegrations(prev => prev.filter(i => i.provider !== provider))
    } catch { /* error */ }
  }

  const isConnected = (provider) => integrations.some(i => i.provider === provider)
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

      {/* Integrations */}
      <section className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <Link2 size={20} className="text-vida-600" />
            Connected Integrations
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">Sync your calendar and notes for smarter planning</p>
        </div>
        <div className="p-6 space-y-4">
          {/* Google Calendar */}
          <div className="flex items-center justify-between p-4 rounded-xl border border-gray-200 hover:border-gray-300 transition-colors">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center flex-shrink-0">
                <Calendar size={24} className="text-blue-600" />
              </div>
              <div>
                <div className="text-sm font-semibold text-gray-900">Google Calendar</div>
                <div className="text-xs text-gray-500">
                  {isConnected('google_calendar')
                    ? `Connected${getIntegration('google_calendar')?.last_sync ? ` · Last synced ${new Date(getIntegration('google_calendar').last_sync).toLocaleString()}` : ''}`
                    : 'Import events, deadlines, and meetings'}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {isConnected('google_calendar') ? (
                <>
                  <button onClick={() => syncIntegration('google_calendar')} disabled={syncing === 'google_calendar'}
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

          {/* Notion */}
          <div className="flex items-center justify-between p-4 rounded-xl border border-gray-200 hover:border-gray-300 transition-colors">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-gray-100 flex items-center justify-center flex-shrink-0">
                <BookOpen size={24} className="text-gray-800" />
              </div>
              <div>
                <div className="text-sm font-semibold text-gray-900">Notion</div>
                <div className="text-xs text-gray-500">
                  {isConnected('notion')
                    ? `Connected${getIntegration('notion')?.last_sync ? ` · Last synced ${new Date(getIntegration('notion').last_sync).toLocaleString()}` : ''}`
                    : 'Sync projects, tasks, and knowledge base'}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {isConnected('notion') ? (
                <>
                  <button onClick={() => syncIntegration('notion')} disabled={syncing === 'notion'}
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
