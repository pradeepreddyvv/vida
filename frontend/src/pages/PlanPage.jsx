import { useState, useEffect } from 'react'
import { api, pollJob } from '../lib/api'
import { Sparkles, Check, RefreshCw, Clock, Loader2, AlertCircle } from 'lucide-react'

export default function PlanPage() {
  const [plan, setPlan] = useState(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [accepting, setAccepting] = useState(false)

  const load = async () => {
    try {
      const data = await api.get('/api/plan/current')
      setPlan(data.plan)
    } catch (e) {
      console.error(e)
    }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const generate = async () => {
    setGenerating(true)
    try {
      const { job_id } = await api.post('/api/plan/generate', {})
      await pollJob(job_id, { interval: 3000, maxAttempts: 30 })
      await load()
    } catch (e) {
      alert('Failed: ' + e.message)
    }
    setGenerating(false)
  }

  const replan = async () => {
    setGenerating(true)
    try {
      const { job_id } = await api.post('/api/plan/replan', { reason: 'My day changed' })
      await pollJob(job_id, { interval: 3000, maxAttempts: 30 })
      await load()
    } catch (e) {
      alert('Replan failed: ' + e.message)
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
      alert('Accept failed: ' + e.message)
    }
    setAccepting(false)
  }

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="animate-spin text-vida-600" size={32} /></div>

  return (
    <div className="max-w-4xl">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Daily Plan</h1>
          <p className="text-gray-500 mt-1">{new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={generate}
            disabled={generating}
            className="px-4 py-2 bg-vida-600 text-white rounded-lg hover:bg-vida-700 disabled:opacity-50 flex items-center gap-2 text-sm"
          >
            {generating ? <Loader2 className="animate-spin" size={16} /> : <Sparkles size={16} />}
            {plan ? 'Regenerate' : 'Generate Plan'}
          </button>
          {plan && plan.status === 'accepted' && (
            <button onClick={replan} disabled={generating} className="px-4 py-2 bg-amber-500 text-white rounded-lg hover:bg-amber-600 disabled:opacity-50 flex items-center gap-2 text-sm">
              <RefreshCw size={16} /> My Day Changed
            </button>
          )}
        </div>
      </div>

      {!plan ? (
        <div className="text-center py-16 bg-white rounded-xl border">
          <Sparkles className="mx-auto text-gray-300 mb-4" size={48} />
          <h3 className="text-lg font-medium text-gray-600">No plan yet</h3>
          <p className="text-gray-400 mt-1">Click "Generate Plan" to create your daily schedule</p>
        </div>
      ) : (
        <div className="space-y-6">
          {plan.status === 'draft' && (
            <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl flex items-center justify-between">
              <div>
                <div className="font-medium text-amber-800">Draft Plan</div>
                <div className="text-sm text-amber-600">Review the plan below and accept it to create time blocks</div>
              </div>
              <button
                onClick={accept}
                disabled={accepting}
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

          <div className="grid grid-cols-4 gap-4">
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
                  <div className="text-sm">{obj.issue}</div>
                  <div className="text-xs text-gray-500 mt-1">Severity: {obj.severity} | Fix: {obj.suggested_fix}</div>
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
