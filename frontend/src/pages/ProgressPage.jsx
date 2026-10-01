import { useState, useEffect } from 'react'
import { api, pollJob } from '../lib/api'
import { BarChart3, Target, Flame, FileText, ChevronDown, ChevronUp, Loader2 } from 'lucide-react'

const categoryColors = {
  career: 'bg-blue-100 text-blue-700',
  health: 'bg-green-100 text-green-700',
  learning: 'bg-purple-100 text-purple-700',
  personal: 'bg-orange-100 text-orange-700',
  financial: 'bg-yellow-100 text-yellow-700',
}

export default function ProgressPage() {
  const [progress, setProgress] = useState(null)
  const [reports, setReports] = useState([])
  const [expandedReport, setExpandedReport] = useState(null)
  const [reportDetail, setReportDetail] = useState({})
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => { fetchData() }, [])

  async function fetchData() {
    setLoading(true)
    setError(null)
    try {
      const [prog, reps] = await Promise.all([
        api.get('/api/progress'),
        api.get('/api/reports'),
      ])
      setProgress(prog)
      setReports(reps.reports || [])
    } catch (e) {
      setError(e.message)
    }
    setLoading(false)
  }

  async function generateReport() {
    setGenerating(true)
    try {
      const { job_id } = await api.post('/api/reports/daily', {})
      await pollJob(job_id)
      await fetchData()
    } catch (e) {
      setError(e.message)
    }
    setGenerating(false)
  }

  async function toggleReport(date) {
    if (expandedReport === date) {
      setExpandedReport(null)
      return
    }
    if (!reportDetail[date]) {
      try {
        const data = await api.get(`/api/reports/${date}`)
        setReportDetail(prev => ({ ...prev, [date]: data }))
      } catch (e) {
        setError(e.message)
        return
      }
    }
    setExpandedReport(date)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-vida-600" size={32} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
        {error}
        <button onClick={fetchData} className="ml-4 underline">Retry</button>
      </div>
    )
  }

  const bestStreak = progress?.habits?.length
    ? Math.max(...progress.habits.map(h => h.streak_best || 0))
    : 0

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <h1 className="text-2xl font-bold text-gray-900">Progress</h1>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <KPICard
          icon={<BarChart3 size={20} />}
          label="Task Completion"
          value={`${progress?.task_completion_pct || 0}%`}
          sub={`${progress?.tasks_completed || 0} / ${progress?.tasks_total || 0} tasks`}
        />
        <KPICard
          icon={<Target size={20} />}
          label="Active Goals"
          value={progress?.active_goals_count || 0}
          sub={`${progress?.goals?.length || 0} total goals`}
        />
        <KPICard
          icon={<Flame size={20} />}
          label="Best Streak"
          value={`${bestStreak} days`}
          sub={`${progress?.habits?.length || 0} habits tracked`}
        />
      </div>

      {/* Goals */}
      <section>
        <h2 className="text-lg font-semibold text-gray-800 mb-3">Goals</h2>
        {(!progress?.goals || progress.goals.length === 0) ? (
          <div className="bg-white rounded-lg border p-6 text-center text-gray-500">
            No goals yet. Add goals in the Library.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {progress.goals.map(g => (
              <div key={g.goal_id} className="bg-white rounded-lg border p-4 space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-medium text-gray-900">{g.title}</h3>
                    <span className={`inline-block mt-1 px-2 py-0.5 rounded text-xs font-medium ${categoryColors[g.category] || 'bg-gray-100 text-gray-600'}`}>
                      {g.category}
                    </span>
                  </div>
                  {g.target_date && (
                    <span className="text-xs text-gray-500">Due {g.target_date}</span>
                  )}
                </div>
                <div>
                  <div className="flex justify-between text-xs text-gray-500 mb-1">
                    <span>{g.completed_tasks}/{g.total_tasks} tasks</span>
                    <span>{g.progress_pct}%</span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-2">
                    <div
                      className="bg-vida-600 h-2 rounded-full transition-all"
                      style={{ width: `${Math.min(100, g.progress_pct)}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Habits */}
      <section>
        <h2 className="text-lg font-semibold text-gray-800 mb-3">Habits</h2>
        {(!progress?.habits || progress.habits.length === 0) ? (
          <div className="bg-white rounded-lg border p-6 text-center text-gray-500">
            No habits tracked yet.
          </div>
        ) : (
          <div className="bg-white rounded-lg border divide-y">
            {progress.habits.map(h => (
              <div key={h.habit_id} className="flex items-center justify-between px-4 py-3">
                <div className="flex items-center gap-3">
                  <Flame size={16} className={h.streak_current > 0 ? 'text-orange-500' : 'text-gray-300'} />
                  <span className="text-sm font-medium text-gray-900">{h.name}</span>
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <span className="text-gray-500">Current: <span className="font-medium text-gray-700">{h.streak_current}d</span></span>
                  <span className="text-gray-500">Best: <span className="font-medium text-gray-700">{h.streak_best}d</span></span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Reports */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-gray-800">Daily Reports</h2>
          <button
            onClick={generateReport}
            disabled={generating}
            className="px-4 py-2 bg-vida-600 text-white text-sm font-medium rounded-lg hover:bg-vida-700 disabled:opacity-50 flex items-center gap-2"
          >
            {generating && <Loader2 size={14} className="animate-spin" />}
            {generating ? 'Generating...' : 'Generate Today\'s Report'}
          </button>
        </div>

        {reports.length === 0 ? (
          <div className="bg-white rounded-lg border p-6 text-center text-gray-500">
            No reports yet. Generate your first daily report.
          </div>
        ) : (
          <div className="bg-white rounded-lg border divide-y">
            {reports.map(r => (
              <div key={r.date}>
                <button
                  onClick={() => toggleReport(r.date)}
                  className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 text-left"
                >
                  <div className="flex items-center gap-3">
                    <FileText size={16} className="text-gray-400" />
                    <span className="text-sm font-medium text-gray-900">{r.date}</span>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-xs text-gray-500">
                      {r.completed_tasks_count}/{r.planned_tasks_count} tasks
                    </span>
                    <span className="text-xs text-gray-500">
                      {r.habits_completed}/{r.habits_total} habits
                    </span>
                    {expandedReport === r.date ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </div>
                </button>

                {expandedReport === r.date && reportDetail[r.date] && (
                  <div className="px-4 pb-4 space-y-3 bg-gray-50">
                    {reportDetail[r.date].ai_narrative && (
                      <p className="text-sm text-gray-700">{reportDetail[r.date].ai_narrative}</p>
                    )}
                    {reportDetail[r.date].accomplishments?.length > 0 && (
                      <div>
                        <h4 className="text-xs font-semibold text-gray-500 uppercase mb-1">Accomplishments</h4>
                        <ul className="list-disc list-inside text-sm text-gray-700 space-y-0.5">
                          {reportDetail[r.date].accomplishments.map((a, i) => <li key={i}>{a}</li>)}
                        </ul>
                      </div>
                    )}
                    {reportDetail[r.date].improvement_suggestion && (
                      <div className="bg-vida-50 rounded p-3">
                        <h4 className="text-xs font-semibold text-vida-700 uppercase mb-1">Suggestion</h4>
                        <p className="text-sm text-vida-700">{reportDetail[r.date].improvement_suggestion}</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

function KPICard({ icon, label, value, sub }) {
  return (
    <div className="bg-white rounded-lg border p-5">
      <div className="flex items-center gap-2 text-gray-500 mb-2">
        {icon}
        <span className="text-sm font-medium">{label}</span>
      </div>
      <div className="text-2xl font-bold text-gray-900">{value}</div>
      <div className="text-xs text-gray-500 mt-1">{sub}</div>
    </div>
  )
}
