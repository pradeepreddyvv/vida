import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { FolderOpen, Plus, CheckCircle2, Circle, FileText, CalendarDays } from 'lucide-react'

const day = () => new Date().toLocaleDateString('en-CA')
export default function ProjectsPage() {
  const [projects, setProjects] = useState([]), [tasks, setTasks] = useState([]), [notes, setNotes] = useState([])
  const [selected, select] = useState(() => sessionStorage.getItem('vida_project') || ''), [form, setForm] = useState(null), [error, setError] = useState(''), [busy, setBusy] = useState(false)
  const [loaded, setLoaded] = useState(false)
  async function load() {
    try {
      const [p,t,n] = await Promise.all([api.get('/api/goals'), api.get('/api/tasks'), api.get('/api/documents')])
      setProjects(p.goals || []); setTasks(t.tasks || []); setNotes(n.documents || []); setLoaded(true)
    } catch(e) { setError(e.message) }
  }
  useEffect(() => { load(); window.addEventListener('vida:changed', load); return () => window.removeEventListener('vida:changed', load) }, [])
  useEffect(() => { sessionStorage.setItem('vida_project', selected) }, [selected])
  const current = projects.find(p => p.goal_id === selected)
  const shownTasks = tasks.filter(t => selected ? t.goal_id === selected : !t.goal_id)
  const shownNotes = notes.filter(n => n.file_type === 'note' && (selected ? n.goal_id === selected : !n.goal_id))
  async function save(e) {
    e.preventDefault(); setBusy(true); setError('')
    const values = Object.fromEntries(new FormData(e.currentTarget))
    try {
      if(form === 'project') {
        const p = await api.post('/api/goals', {title:values.title, description:values.text, category:'project'})
        select(p.goal_id)
      } else if(form === 'task') await api.post('/api/tasks', {title:values.title, description:values.text, goal_id:selected || null, due_date:values.date || null, estimated_minutes:Number(values.minutes || 30), priority:'medium'})
      else if(form === 'note') await api.post('/api/notes', {title:values.title, text:values.text, goal_id:selected || null})
      else await api.post('/api/calendar/blocks', {title:values.title, date:values.date, start_time:values.start, end_time:values.end, block_type:'busy', locked:true})
      setForm(null); await load()
    } catch(e) { setError(e.message) }
    setBusy(false)
  }
  async function toggle(t) {
    setBusy(true)
    try { await api.put('/api/tasks/'+t.task_id, {status:t.status === 'done' ? 'todo' : 'done'}); await load() }
    catch(e) { setError(e.message) }
    setBusy(false)
  }
  return <div className="max-w-5xl mx-auto space-y-6">
    <header><p className="text-xs uppercase tracking-widest text-vida-600 font-semibold">One place for the details</p><h1 className="text-3xl font-bold mt-2">Projects & notes</h1><p className="text-gray-500 mt-2">Keep next actions and decisions together. Ask Vida about your saved notes in the chat.</p></header>
    {error && <p role="alert" className="p-4 bg-red-50 text-red-800 rounded-xl">{error}</p>}
    <div className="flex flex-wrap gap-2">
      <button onClick={() => select('')} className={`px-4 py-2 rounded-full border ${!selected ? 'bg-vida-600 text-white' : 'bg-white'}`}>Inbox</button>
      {projects.map(p => <button key={p.goal_id} onClick={() => select(p.goal_id)} className={`px-4 py-2 rounded-full border ${selected === p.goal_id ? 'bg-vida-600 text-white' : 'bg-white'}`}>{p.title}</button>)}
      <button onClick={() => setForm('project')} className="px-4 py-2 rounded-full border border-dashed flex gap-2 items-center"><Plus size={16}/> New project</button>
    </div>
    <section className="bg-white rounded-2xl border p-5 space-y-4">
      <div className="flex gap-3 items-center"><FolderOpen className="text-vida-600"/><div><h2 className="font-semibold text-xl">{current?.title || 'Inbox'}</h2><p className="text-sm text-gray-500">{current?.description || 'Capture loose tasks and notes before deciding where they belong.'}</p></div></div>
      <div className="flex gap-2 flex-wrap">{[['task','Add task',Plus],['note','Add note',FileText],['event','Add calendar commitment',CalendarDays]].map(([key,label,Icon]) => <button key={key} onClick={() => setForm(key)} className="px-3 py-2 border rounded-lg text-sm flex gap-2 items-center"><Icon size={16}/>{label}</button>)}</div>
      {form && <form onSubmit={save} className="bg-gray-50 border rounded-xl p-4 space-y-3">
        <h3 className="font-semibold">{form === 'event' ? 'Calendar commitment' : 'New '+form}</h3>
        <label className="block text-sm">Title<input name="title" required maxLength={300} className="block border rounded-lg p-2 w-full mt-1" autoFocus /></label>
        {form !== 'event' && <label className="block text-sm">{form === 'note' ? 'Notes and decisions' : 'Details'}<textarea name="text" required={form === 'note'} rows={4} className="block border rounded-lg p-2 w-full mt-1" /></label>}
        {(form === 'task' || form === 'event') && <label className="block text-sm">{form === 'task' ? 'Due date (optional)' : 'Date'}<input name="date" type="date" defaultValue={form === 'event' ? day() : ''} required={form === 'event'} className="block border rounded-lg p-2 mt-1" /></label>}
        {form === 'task' && <label className="block text-sm">Estimated minutes<input name="minutes" type="number" min="5" max="480" defaultValue="30" className="block border rounded-lg p-2 mt-1" /></label>}
        {form === 'event' && <div className="flex gap-3"><label>Start<input className="block border rounded p-2" name="start" type="time" required defaultValue="09:00"/></label><label>End<input className="block border rounded p-2" name="end" type="time" required defaultValue="10:00"/></label></div>}
        <div className="flex gap-3"><button disabled={busy} className="bg-vida-600 text-white px-4 py-2 rounded-lg disabled:opacity-50">{busy ? 'Saving…' : 'Save'}</button><button type="button" onClick={() => setForm(null)} disabled={busy}>Cancel</button></div>
        {form === 'event' && <p className="text-xs text-gray-500">Saved in Vida for planning. This does not create a Google Calendar event.</p>}
      </form>}
    </section>
    <section><h2 className="font-semibold mb-3">Next actions <span className="text-gray-400">{shownTasks.filter(t=>t.status!=='done').length}</span></h2>
      <div className="bg-white border rounded-xl divide-y">{shownTasks.map(t=><div key={t.task_id} className="flex items-start gap-3 p-4"><button disabled={busy} onClick={()=>toggle(t)} aria-label={(t.status==='done'?'Reopen ':'Complete ')+t.title} className="text-vida-600 mt-1">{t.status==='done'?<CheckCircle2 size={20}/>:<Circle size={20}/>}</button><div><p className={t.status==='done'?'line-through text-gray-400':'font-medium'}>{t.title}</p><select aria-label={"Project for " + t.title} value={t.goal_id || ""} disabled={busy} onChange={async e => { setBusy(true); try { await api.put("/api/tasks/"+t.task_id,{goal_id:e.target.value || null}); await load() } catch(e) {setError(e.message)} finally {setBusy(false)} }} className="text-xs border rounded p-1 mt-2"><option value="">Inbox</option>{projects.map(p => <option key={p.goal_id} value={p.goal_id}>{p.title}</option>)}</select><p className="text-xs text-gray-500 mt-1">{t.estimated_minutes || 30} minutes{t.due_date ? ' · Due '+t.due_date : ''}</p>{t.description && <p className="text-sm text-gray-600 mt-2 whitespace-pre-wrap">{t.description}</p>}</div></div>)}{!shownTasks.length&&<p className="p-5 text-sm text-gray-500">{loaded?'No tasks yet. Add the next small action.':'Loading…'}</p>}</div>
    </section>
    <section><h2 className="font-semibold mb-3">Notes & decisions</h2><div className="space-y-3">{shownNotes.map(n=><article key={n.doc_id} className="bg-white border rounded-xl p-5"><h3 className="font-medium">{n.file_name}</h3><p className="text-sm text-gray-600 whitespace-pre-wrap mt-2">{n.text}</p><p className="text-xs text-vida-600 mt-3">Available to Ask Vida</p></article>)}{!shownNotes.length&&<p className="p-5 border rounded-xl text-sm text-gray-500">Save meeting notes, requirements, links, and decisions here.</p>}</div></section>
  </div>
}
