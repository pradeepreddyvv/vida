import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { api, pollJob } from '../lib/api'
import { Sparkles, Check, RefreshCw, Clock, Loader2, AlertCircle } from 'lucide-react'

export default function PlanPage() {
  const [date, setDate] = useState(() => {
    const requested = new URLSearchParams(window.location.search).get('date')
    return /^\d{4}-\d{2}-\d{2}$/.test(requested || '') ? requested : new Date().toLocaleDateString('en-CA')
  })
  const [context, setContext] = useState(null)
  const [error, setError] = useState('')
  const [focus, setFocus] = useState([])
  const [hours, setHours] = useState({day_start:'09:00',day_end:'17:00'})
  const [saving, setSaving] = useState(false)
  const [plan, setPlan] = useState(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [accepting, setAccepting] = useState(false)

  const load = async () => {
    try {
      const [data, ctx] = await Promise.all([api.get('/api/plan/current?date=' + date), api.get('/api/plan/context?date=' + date)])
      setPlan(data.plan); setContext(ctx); setFocus(ctx.focus_task_ids || [])
      setHours({day_start:ctx.profile.day_start, day_end:ctx.profile.day_end})
      sessionStorage.setItem('vida_plan_date', date)
    } catch (e) {
      setError(e.message)
    }
    setLoading(false)
  }

  useEffect(() => { load(); const refresh = () => load(); window.addEventListener('vida:changed', refresh); return () => window.removeEventListener('vida:changed', refresh) }, [date])
  const saveFocus = async () => {
    setSaving(true); setError('')
    try { await api.put('/api/profile', {...hours, planning_focus_task_ids:focus}); await load() }
    catch (e) { setError(e.message) } finally { setSaving(false) }
  }
  const syncCalendar = async () => {
    setGenerating(true); setError('')
    try { const job = await api.post('/api/integrations/google_calendar/sync', {}); await pollJob(job.job_id); await load() }
    catch (e) { setError(e.message) } finally { setGenerating(false) }
  }

  const generate = async () => {
    setGenerating(true)
    setError('')
    try {
      const { job_id } = await api.post('/api/plan/generate', {date})
      await pollJob(job_id, { interval: 3000, maxAttempts: 30 })
      await load()
    } catch (e) {
      setError(e.message)
    }
    setGenerating(false)
  }

  const replan = async () => {
    setGenerating(true)
    setError('')
    try {
      const { job_id } = await api.post('/api/plan/replan', { date, reason: 'My day changed' })
      await pollJob(job_id, { interval: 3000, maxAttempts: 30 })
      await load()
    } catch (e) {
      setError(e.message)
    }
    setGenerating(false)
  }

  const accept = async () => {
    if (!plan) return
    setAccepting(true)
    try {
      await api.post('/api/plan/accept', { date: plan.date, revision: plan.revision })
      await load()
    } catch (e) {
      setError(e.message)
    }
    setAccepting(false)
  }

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="animate-spin text-vida-600" size={32} /></div>

  return (
    <div className="max-w-4xl">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Daily Plan</h1><label className="text-sm">Plan date <input aria-label="Plan date" type="date" value={date} onChange={e => setDate(e.target.value)} className="border rounded p-2 ml-2" /></label>
          <p className="text-gray-500 mt-1">{new Date(date + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={generate}
            disabled={generating || saving || !!context?.blockers?.length}
            className="px-4 py-2 bg-vida-600 text-white rounded-lg hover:bg-vida-700 disabled:opacity-50 flex items-center gap-2 text-sm"
          >
            {generating ? <Loader2 className="animate-spin" size={16} /> : <Sparkles size={16} />}
            {plan ? 'Regenerate' : 'Generate Plan'}
          </button>
          {plan && plan.status === 'accepted' && (
            <button onClick={replan} disabled={generating || saving || !!context?.blockers?.length} className="px-4 py-2 bg-amber-500 text-white rounded-lg hover:bg-amber-600 disabled:opacity-50 flex items-center gap-2 text-sm">
              <RefreshCw size={16} /> My Day Changed
            </button>
          )}
        </div>
      </div>

      {error && <div role="alert" className="p-4 mb-4 bg-red-50 text-red-800 rounded-xl">{error}</div>}
      {context && <section className="bg-white border rounded-xl p-5 mb-6 space-y-4">
        <div className="flex flex-wrap justify-between gap-3"><div><h2 className="font-semibold">Your day, grounded in your calendar</h2><p className="text-sm text-gray-500">{context.selected_calendars.length} selected calendars · {context.profile.timezone} · Next 7 days</p><p className="text-xs text-gray-500">{context.last_synced_at ? `Last synced ${new Date(context.last_synced_at).toLocaleString()}` : 'Calendar has not been synced yet'}</p></div><button className="text-vida-700 underline text-sm" disabled={generating} onClick={syncCalendar}>Refresh calendar</button></div>
        {context.blockers.length > 0 && <div className="bg-amber-50 p-3 rounded-lg text-sm space-y-1">{context.blockers.map(x => <p key={x}>{x}</p>)}{(!context.google_connected || !context.selected_calendars.length) && <Link className="underline" to="/settings">Connect and choose calendars</Link>}</div>}
        {context.warnings?.map(w => <p key={w} className="bg-blue-50 p-3 rounded-lg text-sm">{w}</p>)}
        <h3 className="font-medium text-sm">Which tasks should Vida prioritize?</h3><p className="text-sm text-gray-500">Plan whenever you like. These preferred hours only control when tasks are scheduled. Choose your focus and hours, then save. Vida only schedules these tasks and asks you to approve the draft.</p>
        <div className="max-h-56 overflow-auto space-y-2">{context.tasks.map(t => <label key={t.task_id} className="flex items-center gap-3 text-sm"><input type="checkbox" checked={focus.includes(t.task_id)} onChange={e => setFocus(v => e.target.checked ? [...v,t.task_id] : v.filter(id => id !== t.task_id))}/><span>{t.title}<span className="text-gray-500"> · {t.estimated_minutes}m{t.due_date ? ` · Due ${t.due_date}` : ''}</span></span></label>)}{!context.tasks.length && <Link className="text-sm underline text-vida-700" to="/projects">Add tasks to a project to get started</Link>}</div>
        <div className="flex flex-wrap gap-3 items-center"><label className="text-sm">Start <input aria-label="Planning start time" type="time" value={hours.day_start} onChange={e => setHours(v => ({...v,day_start:e.target.value}))} className="border rounded p-2"/></label><label className="text-sm">End <input aria-label="Planning end time" type="time" value={hours.day_end} onChange={e => setHours(v => ({...v,day_end:e.target.value}))} className="border rounded p-2"/></label><button disabled={saving || generating} onClick={saveFocus} className="bg-vida-600 text-white rounded-lg px-4 py-2 text-sm">{saving ? 'Saving…' : 'Save focus & hours'}</button></div>
        <p className="text-sm text-gray-600">{context.available_minutes} minutes available around existing commitments.</p>
        <h3 className="font-medium text-sm">Existing commitments</h3>{context.existing_blocks.filter(b => b.source !== 'planner').map(b => <div key={b.block_id} className="flex justify-between gap-3 bg-blue-50 rounded-lg p-3 text-sm"><span>{b.title}</span><span>{b.start_time}–{b.end_time}</span></div>)}{!context.existing_blocks.length && <p className="text-sm text-gray-500">No imported commitments for this date. Refresh the calendar to check for updates.</p>}
      </section>}
      {generating && <p role="status" className="mb-4 text-sm text-vida-700">Refreshing your calendar and preparing your draft. Nothing is applied until you accept.</p>}
      {!plan ? (
        <div className="text-center py-16 bg-white rounded-xl border">
          <Sparkles className="mx-auto text-gray-300 mb-4" size={48} />
          <h3 className="text-lg font-medium text-gray-600">No plan yet</h3>
          <p className="text-gray-400 mt-1">Choose your focus above, then generate a draft around your real commitments</p>
        </div>
      ) : (
        <div className="space-y-6">
          {plan.status === 'draft' && (
            <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl flex items-center justify-between">
              <div>
                <div className="font-medium text-amber-800">Draft Plan</div>
                <div className="text-sm text-amber-600">{plan.blocks?.length ? 'Review the plan below and accept it to create time blocks' : 'No time blocks to apply. Extend your hours or choose another date to schedule these tasks.'}</div>
              </div>
              <button
                onClick={accept}
                disabled={accepting || !plan.blocks?.length}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center gap-2 text-sm"
              >
                {accepting ? <Loader2 className="animate-spin" size={16} /> : <Check size={16} />}
                Accept Plan
              </button>
            </div>
          )}

          {plan.status === 'accepted' && (
            <div className="p-3 bg-green-50 border border-green-200 rounded-lg flex items-center gap-2 text-green-700 text-sm">
              <Check size={16} /> Plan accepted
            </div>
          )}

          {plan.explanation && (
            <div className="p-4 bg-vida-50 rounded-xl">
              <div className="text-sm font-medium text-vida-700 mb-1">Plan Summary</div>
              <p className="text-sm text-gray-700">{plan.explanation}</p>
            </div>
          )}

          <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
            <MiniStat label="Available" value={`${plan.total_available_minutes}m`} />
            <MiniStat label="Planned" value={`${plan.total_planned_minutes}m`} />
            <MiniStat label="Breaks" value={`${plan.total_break_minutes}m`} />
            <MiniStat label="Buffer" value={`${plan.total_buffer_minutes}m`} />
          </div>

          <div>
            <h2 className="text-lg font-semibold mb-3">Schedule</h2>
            <div className="space-y-2">
              {(plan.blocks || []).map((block, i) => (
                <div key={i} className={`p-3 rounded-lg border flex items-center gap-3 ${
                  block.block_type === 'task' ? 'bg-white border-gray-200' :
                  block.block_type === 'break' ? 'bg-amber-50 border-amber-200' :
                  'bg-gray-50 border-gray-200'
                }`}>
                  <Clock size={16} className="text-gray-400 flex-shrink-0" />
                  <div className="flex-1">
                    <span className="text-sm font-medium">{block.title}</span>
                  </div>
                  <span className="text-sm text-gray-500">{block.start_time} - {block.end_time}</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    block.block_type === 'task' ? 'bg-vida-100 text-vida-700' :
                    block.block_type === 'break' ? 'bg-amber-100 text-amber-700' :
                    'bg-gray-100 text-gray-600'
                  }`}>{block.block_type}</span>
                </div>
              ))}
            </div>
          </div>

          {plan.deferred_tasks?.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold mb-3 text-amber-700">Deferred Tasks</h2>
              <div className="space-y-2">
                {plan.deferred_tasks.map((t, i) => (
                  <div key={i} className="p-3 bg-amber-50 rounded-lg border border-amber-200">
                    <div className="text-sm font-medium text-gray-800">{t.title}</div>
                    <div className="text-xs text-amber-600 mt-1">{t.reason}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {plan.reviewer_objections?.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold mb-3 flex items-center gap-2"><AlertCircle size={18} className="text-amber-500" /> Reviewer Notes</h2>
              {plan.reviewer_objections.map((obj, i) => (
                <div key={i} className="p-3 bg-amber-50 rounded-lg border border-amber-200 mb-2">
                  <div className="text-sm">{obj.description || obj.issue}</div>
                  <div className="text-xs text-gray-500 mt-1">Severity: {obj.severity} | Fix: {obj.suggestion || obj.suggested_fix}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function MiniStat({ label, value }) {
  return (
    <div className="bg-white border rounded-lg p-3 text-center">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-lg font-bold text-gray-900">{value}</div>
    </div>
  )
}
