import { useState, useEffect } from 'react'
import { api } from '../lib/api'
import {
  Target, ListTodo, Flame, BookOpen, FileText,
  Plus, Loader2, Trash2, X
} from 'lucide-react'

const TABS = [
  { key: 'goals', label: 'Goals', icon: Target },
  { key: 'tasks', label: 'Tasks', icon: ListTodo },
  { key: 'habits', label: 'Habits', icon: Flame },
  { key: 'journal', label: 'Journal', icon: BookOpen },
  { key: 'documents', label: 'Documents', icon: FileText },
]

export default function LibraryPage() {
  const [tab, setTab] = useState('goals')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const endpoints = {
        goals: '/api/goals',
        tasks: '/api/tasks',
        habits: '/api/habits',
        journal: '/api/journal',
        documents: '/api/documents',
      }
      const result = await api.get(endpoints[tab])
      setData(result)
    } catch (e) {
      console.error(e)
    }
    setLoading(false)
  }

  useEffect(() => { load() }, [tab])

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Library</h1>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-4 py-2 bg-vida-600 text-white rounded-lg text-sm font-medium hover:bg-vida-700"
        >
          <Plus size={16} /> Add {tab.slice(0, -1)}
        </button>
      </div>

      <div className="flex gap-1 mb-6 bg-gray-100 p-1 rounded-lg">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => { setTab(key); setShowForm(false) }}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              tab === key ? 'bg-white text-vida-700 shadow-sm' : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <Icon size={16} /> {label}
          </button>
        ))}
      </div>

      {showForm && (
        <AddForm tab={tab} onClose={() => setShowForm(false)} onAdded={() => { setShowForm(false); load() }} />
      )}

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <Loader2 className="animate-spin text-vida-600" size={28} />
        </div>
      ) : (
        <div className="bg-white rounded-xl border">
          {tab === 'goals' && <GoalsList data={data} onRefresh={load} />}
          {tab === 'tasks' && <TasksList data={data} onRefresh={load} />}
          {tab === 'habits' && <HabitsList data={data} />}
          {tab === 'journal' && <JournalList data={data} />}
          {tab === 'documents' && <DocumentsList data={data} />}
        </div>
      )}
    </div>
  )
}

function GoalsList({ data, onRefresh }) {
  const goals = data?.goals || []
  if (!goals.length) return <Empty label="goals" />
  const handleDelete = async (id) => { await api.del('/api/goals/' + id); onRefresh() }
  return (
    <div className="divide-y">
      {goals.map(g => (
        <div key={g.goal_id} className="flex items-center justify-between p-4">
          <div>
            <div className="font-medium text-gray-900">{g.title}</div>
            <div className="text-xs text-gray-500 mt-0.5">{g.status} · {g.category}{g.target_date ? ' · Due ' + g.target_date : ''}</div>
          </div>
          <div className="flex items-center gap-3">
            <span className={'text-xs px-2 py-0.5 rounded ' + (g.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600')}>{g.status}</span>
            <button onClick={() => handleDelete(g.goal_id)} className="text-gray-400 hover:text-red-500"><Trash2 size={14} /></button>
          </div>
        </div>
      ))}
    </div>
  )
}

function TasksList({ data, onRefresh }) {
  const tasks = data?.tasks || []
  if (!tasks.length) return <Empty label="tasks" />
  const handleDelete = async (id) => { await api.del('/api/tasks/' + id); onRefresh() }
  const sc = { todo: 'bg-blue-100 text-blue-700', in_progress: 'bg-amber-100 text-amber-700', done: 'bg-green-100 text-green-700' }
  return (
    <div className="divide-y">
      {tasks.map(t => (
        <div key={t.task_id} className="flex items-center justify-between p-4">
          <div>
            <div className="font-medium text-gray-900">{t.title}</div>
            <div className="text-xs text-gray-500 mt-0.5">{t.priority} · {t.estimated_minutes || '?'}min{t.due_date ? ' · Due ' + t.due_date : ''}</div>
          </div>
          <div className="flex items-center gap-3">
            <span className={'text-xs px-2 py-0.5 rounded ' + (sc[t.status] || 'bg-gray-100 text-gray-600')}>{t.status}</span>
            <button onClick={() => handleDelete(t.task_id)} className="text-gray-400 hover:text-red-500"><Trash2 size={14} /></button>
          </div>
        </div>
      ))}
    </div>
  )
}

function HabitsList({ data }) {
  const habits = data?.habits || []
  if (!habits.length) return <Empty label="habits" />
  return (
    <div className="divide-y">
      {habits.map(h => (
        <div key={h.habit_id} className="flex items-center justify-between p-4">
          <div>
            <div className="font-medium text-gray-900">{h.name}</div>
            <div className="text-xs text-gray-500 mt-0.5">{h.frequency} · {h.category}</div>
          </div>
          <span className="text-xs text-gray-500">{h.completed_today ? 'Done today' : 'Not done'}</span>
        </div>
      ))}
    </div>
  )
}

function JournalList({ data }) {
  const entries = data?.entries || []
  if (!entries.length) return <Empty label="journal entries" />
  return (
    <div className="divide-y">
      {entries.map((e, i) => (
        <div key={i} className="p-4">
          <div className="text-xs text-gray-400 mb-1">{e.date}</div>
          <p className="text-sm text-gray-800">{e.entry_text}</p>
          {e.mood && <span className="inline-block mt-1 text-xs bg-gray-100 px-2 py-0.5 rounded">{e.mood}</span>}
        </div>
      ))}
    </div>
  )
}

function DocumentsList({ data }) {
  const docs = data?.documents || []
  if (!docs.length) return <Empty label="documents" />
  return (
    <div className="divide-y">
      {docs.map(d => (
        <div key={d.doc_id} className="flex items-center justify-between p-4">
          <div className="flex items-center gap-3">
            <FileText size={18} className="text-gray-400" />
            <div>
              <div className="font-medium text-gray-900">{d.file_name}</div>
              <div className="text-xs text-gray-500">{d.file_type} · {Math.round((d.file_size_bytes || 0) / 1024)}KB</div>
            </div>
          </div>
          <span className={'text-xs px-2 py-0.5 rounded ' + (d.kb_status === 'indexed' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700')}>{d.kb_status}</span>
        </div>
      ))}
    </div>
  )
}

function AddForm({ tab, onClose, onAdded }) {
  const [form, setForm] = useState({})
  const [saving, setSaving] = useState(false)
  const set = (k, v) => setForm(prev => ({ ...prev, [k]: v }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      if (tab === 'goals') {
        await api.post('/api/goals', { title: form.title, description: form.description || '', category: form.category || 'personal', priority: form.priority || 'medium', target_date: form.target_date || null })
      } else if (tab === 'tasks') {
        await api.post('/api/tasks', { title: form.title, description: form.description || '', priority: form.priority || 'medium', due_date: form.due_date || null, estimated_minutes: parseInt(form.estimated_minutes || '30') })
      } else if (tab === 'habits') {
        await api.post('/api/habits', { name: form.title, frequency: form.frequency || 'daily', category: form.category || 'other', reason: form.reason || '' })
      } else if (tab === 'journal') {
        await api.post('/api/journal', { entry_text: form.entry_text, mood: form.mood || null })
      } else if (tab === 'documents') {
        const fileInput = document.getElementById('doc-upload')
        if (!fileInput?.files?.[0]) return
        const file = fileInput.files[0]
        const presign = await api.post('/api/documents/presign', { file_name: file.name, file_type: file.name.split('.').pop(), file_size_bytes: file.size })
        await fetch(presign.upload_url, { method: 'PUT', body: file, headers: { 'Content-Type': file.type || 'application/octet-stream' } })
      }
      onAdded()
    } catch (err) { alert(err.message) }
    setSaving(false)
  }

  return (
    <form onSubmit={handleSubmit} className="mb-6 bg-white rounded-xl border p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-gray-800">Add {tab.slice(0, -1)}</h3>
        <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
      </div>
      {(tab === 'goals' || tab === 'tasks') && (
        <>
          <input placeholder="Title" value={form.title || ''} onChange={e => set('title', e.target.value)} className="w-full px-3 py-2 border rounded-lg text-sm" required />
          <input placeholder="Description" value={form.description || ''} onChange={e => set('description', e.target.value)} className="w-full px-3 py-2 border rounded-lg text-sm" />
          <div className="flex gap-3">
            <select value={form.priority || 'medium'} onChange={e => set('priority', e.target.value)} className="px-3 py-2 border rounded-lg text-sm">
              <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option>
            </select>
            <input type="date" value={form[tab === 'goals' ? 'target_date' : 'due_date'] || ''} onChange={e => set(tab === 'goals' ? 'target_date' : 'due_date', e.target.value)} className="px-3 py-2 border rounded-lg text-sm" />
            {tab === 'tasks' && <input type="number" placeholder="Minutes" value={form.estimated_minutes || ''} onChange={e => set('estimated_minutes', e.target.value)} className="w-24 px-3 py-2 border rounded-lg text-sm" />}
          </div>
        </>
      )}
      {tab === 'habits' && (
        <>
          <input placeholder="Habit name" value={form.title || ''} onChange={e => set('title', e.target.value)} className="w-full px-3 py-2 border rounded-lg text-sm" required />
          <div className="flex gap-3">
            <select value={form.frequency || 'daily'} onChange={e => set('frequency', e.target.value)} className="px-3 py-2 border rounded-lg text-sm">
              <option value="daily">Daily</option><option value="weekly">Weekly</option>
            </select>
            <input placeholder="Why?" value={form.reason || ''} onChange={e => set('reason', e.target.value)} className="flex-1 px-3 py-2 border rounded-lg text-sm" />
          </div>
        </>
      )}
      {tab === 'journal' && (
        <>
          <textarea placeholder="Write your thoughts..." value={form.entry_text || ''} onChange={e => set('entry_text', e.target.value)} className="w-full px-3 py-2 border rounded-lg text-sm h-24 resize-none" required />
          <input placeholder="Mood (optional)" value={form.mood || ''} onChange={e => set('mood', e.target.value)} className="w-full px-3 py-2 border rounded-lg text-sm" />
        </>
      )}
      {tab === 'documents' && <input id="doc-upload" type="file" accept=".pdf,.md,.txt" className="text-sm" required />}
      <button type="submit" disabled={saving} className="px-4 py-2 bg-vida-600 text-white rounded-lg text-sm font-medium hover:bg-vida-700 disabled:opacity-50 flex items-center gap-2">
        {saving && <Loader2 size={14} className="animate-spin" />}
        {saving ? 'Saving...' : 'Save'}
      </button>
    </form>
  )
}

function Empty({ label }) {
  return <div className="p-8 text-center text-gray-400 text-sm">No {label} yet. Click "Add" to create one.</div>
}
