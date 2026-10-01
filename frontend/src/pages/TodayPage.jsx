import { useState, useEffect } from 'react'
import { api, pollJob } from '../lib/api'
import { Play, Check, Clock, AlertTriangle, Target, Sparkles, Loader2, ChevronRight } from 'lucide-react'

export default function TodayPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)

  const load = async () => {
    try {
      const d = await api.get('/api/today')
      setData(d)
    } catch (e) {
      console.error(e)
    }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const generatePlan = async () => {
    setGenerating(true)
    try {
      const { job_id } = await api.post('/api/plan/generate', {})
      await pollJob(job_id, { interval: 3000, maxAttempts: 30 })
      await load()
    } catch (e) {
      alert('Plan generation failed: ' + e.message)
    }
    setGenerating(false)
  }

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
      await api.post(`/api/habits/${habitId}/log`, { completed: !completed })
      load()
    } catch (e) {
      console.error(e)
    }
  }

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="animate-spin text-vida-600" size={32} /></div>
  if (!data) return <div className="text-gray-500">Failed to load data.</div>

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
        <p className="text-gray-500 mt-1">{new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}</p>
      </div>

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
        <button
          onClick={generatePlan}
          disabled={generating}
          className="mb-6 px-6 py-3 bg-vida-600 text-white font-medium rounded-lg hover:bg-vida-700 disabled:opacity-50 transition-colors flex items-center gap-2"
        >
          {generating ? <><Loader2 className="animate-spin" size={18} /> Generating plan...</> : <><Sparkles size={18} /> Generate Today's Plan</>}
        </button>
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
            {(data.due_today_tasks || []).map(t => (
              <div key={t.task_id} className="flex items-center gap-3 p-3 bg-white rounded-lg border">
                <button
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
            {(!data.due_today_tasks || data.due_today_tasks.length === 0) && (
              <div className="text-sm text-gray-400 p-4 text-center border border-dashed rounded-lg">No tasks due today</div>
            )}
          </div>

          <h2 className="text-lg font-semibold text-gray-900 mt-6 mb-3">Habits</h2>
          <div className="space-y-2">
            {(data.habits || []).map(h => (
              <div key={h.habit_id} className="flex items-center gap-3 p-3 bg-white rounded-lg border">
                <button
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
