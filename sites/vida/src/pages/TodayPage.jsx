import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, pollJob } from '../lib/api'
import { Play, Check, Clock, AlertTriangle, Target, Sparkles, Loader2, ChevronRight, Calendar, RefreshCw, ExternalLink } from 'lucide-react'

export default function TodayPage({ demo = false }) {
  const [guideKey] = useState(() => 'vida_today_guide_seen:' + (sessionStorage.getItem('vida_user_id') || 'guest'))
  const [guideOpen, setGuideOpen] = useState(() => {
    try { return localStorage.getItem('vida_today_guide_seen:' + (sessionStorage.getItem('vida_user_id') || 'guest')) !== 'true' }
    catch { return true }
  })
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [calendarStatus, setCalendarStatus] = useState(null) // null, 'not_connected', 'connected'
  const [syncing, setSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState(null)

  const load = async () => {
    try {
      const [d, intData] = await Promise.all([
        api.get('/api/today'),
        api.get('/api/integrations').catch(() => ({ integrations: [] })),
      ])
      setData(d)
      const gcal = (intData.integrations || []).find(i => i.provider === 'google_calendar')
      setCalendarStatus(gcal?.status === 'connected' ? 'connected' : 'not_connected')
    } catch (e) {
      console.error(e)
    }
    setLoading(false)
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('connected') === 'google') {
      setCalendarStatus('connected')
      window.history.replaceState({}, '', window.location.pathname)
    }
    load(); window.addEventListener('vida:changed', load); return () => window.removeEventListener('vida:changed', load)
  }, [])

  const connectCalendar = async () => {
    try {
      const data = await api.get('/api/auth/google')
      if (data.url) window.location.href = data.url
    } catch (e) { setError(e.message) }
  }

  const syncCalendar = async () => {
    setSyncing(true)
    setSyncResult(null)
    setError('')
    try {
      const { job_id } = await api.post('/api/integrations/google_calendar/sync', {})
      const result = await pollJob(job_id, { interval: 3000, maxAttempts: 20 })
      const synced = result.result?.synced_events || 0
      setSyncResult({ synced, replanned: !!result.result?.replan })
      await load()
    } catch (e) { setError(e.message) }
    setSyncing(false)
  }

  useEffect(() => {
    if (!data || loading) return
    try { localStorage.setItem(guideKey, 'true') } catch { /* Guide remains usable when storage is unavailable. */ }
  }, [data, loading, guideKey])

  const openPlan = () => navigate('/plan?date=' + encodeURIComponent(data.date))

  const toggleTask = async (taskId, currentStatus) => {
    const newStatus = currentStatus === 'done' ? 'todo' : 'done'
    try {
      await api.put(`/api/tasks/${taskId}`, { status: newStatus })
      load()
    } catch (e) {
      console.error(e)
    }
  }

  const toggleHabit = async (habitId, completed) => {
    try {
      await api.post(`/api/habits/${habitId}/log`, { completed: !completed, date: data.date })
      load()
    } catch (e) {
      console.error(e)
    }
  }

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="animate-spin text-vida-600" size={32} /></div>
  if (!data) return <div className="text-gray-500">Failed to load data.</div>

  const hasTasks = [data.due_today_tasks, data.other_tasks, data.overdue_tasks].some(tasks => tasks?.length)

  const greeting = () => {
    const h = new Date().getHours()
    if (h < 12) return 'Good morning'
    if (h < 17) return 'Good afternoon'
    return 'Good evening'
  }

  return (
    <div className="max-w-4xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">{greeting()}, {data.profile_name || 'there'}!</h1>
        <p className="text-gray-500 mt-1">{new Date(data.date + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}</p>
      </div>

      <details className="mb-6 border rounded-xl bg-white p-5" open={guideOpen} onToggle={event => setGuideOpen(event.currentTarget.open)}>
        <summary className="text-base font-semibold cursor-pointer">Start here · Five steps to get the most out of Vida</summary>
        <p className="text-sm text-gray-600 mt-1 mb-4">{demo ? 'Explore sample tasks, plan your time, and try approved changes locally. No connections needed.' : 'Connect your tools once, then use Vida to capture tasks, plan your time, and track your progress.'}</p>
        <ol className="space-y-3 text-sm">
          <li>{demo ? <><strong>1. Try the Saturday starter in Ask Vida</strong><p className="text-gray-600">Review five proposed changes, then approve them. Sample Calendar and Notion updates stay inside this workspace.</p></> : <><Link className="text-vida-700 font-semibold underline" to="/settings#integrations">1. Connect your tools in Settings</Link><p className="text-gray-600">Connect Google Calendar, select calendars, and sync. Add Notion to create your Vida Tasks and Vida Habits pages.</p></>}</li>
          <li><Link className="text-vida-700 font-semibold underline" to="/projects">2. Capture tasks in Projects</Link><p className="text-gray-600">Group work by project and add realistic durations and due dates. Or tell Ask Vida your brain dump and approve the proposed changes.</p></li>
          <li><Link className="text-vida-700 font-semibold underline" to="/plan">3. Choose your focus in Plan</Link><p className="text-gray-600">Pick a date, a few priority tasks, and your available hours. Save, generate a draft around your calendar, then review and accept.</p></li>
          <li><strong>4. Work from Today</strong><p className="text-gray-600">{demo ? 'Check off sample tasks and habits here. Nothing is sent to Google or Notion.' : 'Check off tasks and habits here. Vida copies those updates to your connected Notion pages automatically.'}</p></li>
          <li><Link className="text-vida-700 font-semibold underline" to="/progress">5. Reflect in Progress</Link><p className="text-gray-600">Review completed work and daily reports. Use Library to find saved notes, and Ask Vida to recall details with sources.</p></li>
        </ol>
        <p className="mt-4 text-xs text-gray-500">Start small: choose 1–3 priorities and leave room for breaks. Plans stay as drafts until you accept; accepting creates time blocks in Vida.</p>
      </details>

      {error && <div role="alert" className="mb-4 p-4 bg-red-50 text-red-800 rounded-xl">{error}</div>}
      {syncResult && (
        <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-xl">
          <div className="text-sm text-green-800">
            <span className="font-medium">Synced {syncResult.synced} calendar events</span>
            {syncResult.replanned && ' — a new draft plan has been created based on your real schedule'}
          </div>
        </div>
      )}

      {calendarStatus === 'connected' && !syncResult && (
        <div className="mb-6 p-4 bg-vida-50 border border-vida-200 rounded-xl flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Calendar size={20} className="text-vida-600" />
            <div>
              <div className="text-sm font-medium text-vida-800">Google Calendar connected</div>
              <div className="text-xs text-vida-600">Sync your events to plan based on your real schedule</div>
            </div>
          </div>
          <button onClick={syncCalendar} disabled={syncing}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-vida-600 rounded-lg hover:bg-vida-700 disabled:opacity-50 transition-colors">
            {syncing ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            {syncing ? 'Syncing...' : 'Sync Now'}
          </button>
        </div>
      )}

      {data.next_action && (
        <div className="mb-6 p-4 bg-vida-50 border border-vida-200 rounded-xl">
          <div className="flex items-center gap-2 text-vida-700 font-medium mb-1">
            <Sparkles size={18} />
            Next Action
          </div>
          <p className="text-gray-800 font-medium">{data.next_action.title}</p>
          <div className="flex gap-3 mt-2 text-sm text-gray-500">
            {data.next_action.due_date && <span>Due: {data.next_action.due_date}</span>}
            <span className="capitalize">{data.next_action.priority} priority</span>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <StatCard
          icon={<Target className="text-vida-600" size={20} />}
          label="Active Goals"
          value={data.goals?.length || 0}
        />
        <StatCard
          icon={<Check className="text-green-600" size={20} />}
          label="Tasks Due Today"
          value={data.due_today_tasks?.length || 0}
        />
        <StatCard
          icon={<Clock className="text-amber-600" size={20} />}
          label="Scheduled Minutes"
          value={data.capacity?.scheduled_minutes || 0}
        />
      </div>

      {!data.current_plan && (
        <section className="mb-6 p-5 bg-white border rounded-xl space-y-3">
          <h2 className="font-semibold text-gray-900">{hasTasks ? 'Choose your focus before planning' : 'What would you like to work on?'}</h2>
          <p className="text-sm text-gray-600">{hasTasks ? 'Select the tasks you want to prioritize and confirm your hours. Vida will build a draft around your calendar for you to review.' : 'Your calendar commitments are already in the schedule below. Add a task, then choose when to work on it. You do not need to create a goal first.'}</p>
          <div className="flex flex-wrap items-center gap-4">
            {hasTasks ? <button onClick={openPlan} className="px-5 py-3 bg-vida-600 text-white font-medium rounded-lg hover:bg-vida-700 flex items-center gap-2"><Sparkles size={18} />Choose tasks & plan today</button> : <Link to="/projects" className="px-5 py-3 bg-vida-600 text-white font-medium rounded-lg hover:bg-vida-700">Add a task</Link>}
            {!hasTasks && <button onClick={openPlan} className="text-sm text-vida-700 underline">View availability</button>}
          </div>
        </section>
      )}

      {data.current_plan && (
        <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-xl">
          <div className="flex items-center gap-2 text-green-700 font-medium">
            <Check size={18} /> Plan Active (Revision {data.current_plan.revision})
          </div>
          {data.current_plan.explanation && <p className="text-sm text-gray-600 mt-1">{data.current_plan.explanation}</p>}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Schedule</h2>
          {data.blocks?.length > 0 ? (
            <div className="space-y-2">
              {data.blocks.map(block => (
                <div key={block.block_id} className={`p-3 rounded-lg border ${
                  block.status === 'completed' ? 'bg-green-50 border-green-200' :
                  block.block_type === 'busy' ? 'bg-red-50 border-red-200' :
                  block.block_type === 'break' ? 'bg-amber-50 border-amber-200' :
                  'bg-white border-gray-200'
                }`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-sm font-medium text-gray-900">{block.title}</span>
                      <span className="text-xs text-gray-500 ml-2">{block.start_time} - {block.end_time}</span>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      block.block_type === 'task' ? 'bg-vida-100 text-vida-700' :
                      block.block_type === 'break' ? 'bg-amber-100 text-amber-700' :
                      'bg-gray-100 text-gray-600'
                    }`}>{block.block_type}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-sm text-gray-400 p-4 text-center border border-dashed rounded-lg">No blocks scheduled</div>
          )}

          {data.overdue_tasks?.length > 0 && (
            <div className="mt-4">
              <h3 className="text-sm font-semibold text-red-600 flex items-center gap-1 mb-2">
                <AlertTriangle size={14} /> Overdue ({data.overdue_tasks.length})
              </h3>
              {data.overdue_tasks.map(t => (
                <div key={t.task_id} className="p-2 bg-red-50 rounded text-sm mb-1">
                  {t.title} <span className="text-red-500">due {t.due_date}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Tasks</h2>
          <div className="space-y-2">
            {[...(data.due_today_tasks || []), ...(data.other_tasks || [])].map(t => (
              <div key={t.task_id} className="flex items-center gap-3 p-3 bg-white rounded-lg border">
                <button
                  aria-label={`${t.status === 'done' ? 'Reopen' : 'Complete'} ${t.title}`}
                  onClick={() => toggleTask(t.task_id, t.status)}
                  className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 ${
                    t.status === 'done' ? 'bg-green-500 border-green-500 text-white' : 'border-gray-300'
                  }`}
                >
                  {t.status === 'done' && <Check size={12} />}
                </button>
                <div className="flex-1 min-w-0">
                  <div className={`text-sm font-medium ${t.status === 'done' ? 'line-through text-gray-400' : 'text-gray-900'}`}>
                    {t.title}
                  </div>
                  <div className="text-xs text-gray-500">{t.estimated_minutes}min | {t.priority}</div>
                </div>
              </div>
            ))}
            {(!data.due_today_tasks?.length && !data.other_tasks?.length) && (
              <div className="text-sm text-gray-400 p-4 text-center border border-dashed rounded-lg">No open tasks. Add one in Projects.</div>
            )}
          </div>

          <h2 className="text-lg font-semibold text-gray-900 mt-6 mb-3">Habits</h2>
          <div className="space-y-2">
            {(data.habits || []).map(h => (
              <div key={h.habit_id} className="flex items-center gap-3 p-3 bg-white rounded-lg border">
                <button
                  aria-label={`${h.completed_today ? 'Uncheck' : 'Check off'} ${h.name}`}
                    onClick={() => toggleHabit(h.habit_id, h.completed_today)}
                  className={`w-5 h-5 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${
                    h.completed_today ? 'bg-green-500 border-green-500 text-white' : 'border-gray-300'
                  }`}
                >
                  {h.completed_today && <Check size={12} />}
                </button>
                <div className="flex-1">
                  <span className="text-sm font-medium text-gray-900">{h.name}</span>
                  {h.streak > 0 && <span className="text-xs text-amber-600 ml-2">{h.streak} day streak</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function StatCard({ icon, label, value }) {
  return (
    <div className="bg-white rounded-xl border p-4">
      <div className="flex items-center gap-2 mb-1">{icon}<span className="text-sm text-gray-500">{label}</span></div>
      <div className="text-2xl font-bold text-gray-900">{value}</div>
    </div>
  )
}
