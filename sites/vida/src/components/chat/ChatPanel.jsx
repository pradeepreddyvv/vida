import { useEffect, useRef, useState } from 'react'
import { X, Send, Sparkles, Mic, MicOff, FileText, Check, Loader2, RotateCcw, ChevronDown, ExternalLink } from 'lucide-react'
import { api, pollJob } from '../../lib/api'
import { nextSaturday } from '../../lib/demoDates'

const labels = { notion_append: 'Append to Notion page', notion_replace: 'Replace Notion page text', notion_rename: 'Rename Notion page', notion_create: 'Create Notion page', set_focus: 'Choose planning priorities', update_task: 'Update task', save_note: 'Save a project note', web_search: 'Search the public web', create_task: 'Create task', complete_task: 'Complete task', create_journal: 'Save journal entry', create_event: 'Add calendar event', update_event: 'Update calendar event', delete_event: 'Delete calendar event' }
function ResultLink({ url }) {
  if (url === '/library' || /^\/plan\?date=\d{4}-\d{2}-\d{2}$/.test(url || '')) return <a className="result-button" href={url}>Open demo result<ExternalLink size={13} aria-hidden="true" /></a>
  if (!url?.startsWith('https://')) return null
  let isNotion = false
  try { const host = new URL(url).hostname; isNotion = ['notion.so', 'notion.com'].some(domain => host === domain || host.endsWith('.' + domain)) } catch { return null }
  return <a className="result-button" href={url} target="_blank" rel="noopener noreferrer" aria-label={isNotion ? 'Open result in Notion (new tab)' : 'Open result (new tab)'}>{isNotion ? 'Open in Notion' : 'Open result'}<ExternalLink size={13} aria-hidden="true" /></a>
}

export default function ChatPanel({ onClose, visible, demo = false }) {
  const demoRestricted = p => p.error?.startsWith('Test workspaces cannot')
  const [destinationsOpen, setDestinationsOpen] = useState(false)
  const [destinations, setDestinations] = useState(null)
  const [destinationError, setDestinationError] = useState('')
  const [calendarChoice, setCalendarChoice] = useState('')
  const [pageChoice, setPageChoice] = useState('')
  const [capabilities, setCapabilities] = useState({})
  const starterKey = `vida_saturday_starter:${sessionStorage.getItem('vida_user_id') || 'guest'}`
  const [starterDismissed, setStarterDismissed] = useState(() => {
    try { return localStorage.getItem(starterKey) === 'seen' } catch { return false }
  })
  const [preparingDemo, setPreparingDemo] = useState(false)
  function dismissStarter() {
    setStarterDismissed(true)
    try { localStorage.setItem(starterKey, 'seen') } catch {}
  }
  const [workflows, setWorkflows] = useState([])
  const [requests, setRequests] = useState([])
  const [requestStage, setRequestStage] = useState('Waiting to start')
  const [notices, setNotices] = useState([])
  const [activityError, setActivityError] = useState('')
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [listening, setListening] = useState(false)
  const [sourcesOpen, setSourcesOpen] = useState(null)
  const [busyAction, setBusyAction] = useState(null)
  const recognition = useRef(null)
  const inputRef = useRef(null)
  const scrollRef = useRef(null)
  const sendingRef = useRef(false)
  const mounted = useRef(true)
  const speechAvailable = typeof window !== 'undefined' && !!(window.SpeechRecognition || window.webkitSpeechRecognition)

  async function loadDestinations() {
    setDestinationsOpen(true); setDestinations(null); setDestinationError('')
    setCalendarChoice(''); setPageChoice('')
    try {
      if (demo) { setDestinations({calendars:[{id:'demo-calendar',title:'Sample calendar · not synced'}],pages:[{notion_id:'demo-notion',file_name:'Vida demo test · sample'}]}); return }
      const integrations = await api.get('/api/integrations')
      const connected = p => integrations.integrations?.some(i => i.provider === p && i.status === 'connected')
      const [calendars, docs] = await Promise.allSettled([
        connected('google_calendar') ? api.get('/api/integrations/google_calendar/calendars') : Promise.resolve({calendars:[],selected:[]}),
        connected('notion') ? api.get('/api/documents') : Promise.resolve({documents:[]})
      ])
      const c = calendars.status === 'fulfilled' ? calendars.value : {calendars:[],selected:[]}
      const d = docs.status === 'fulfilled' ? docs.value : {documents:[]}
      setDestinations({calendars:c.calendars.filter(x => c.selected.includes(x.id)), pages:d.documents.filter(x => x.source === 'notion' && x.notion_id)})
      if (calendars.status === 'rejected' || docs.status === 'rejected') setDestinationError('Some options could not load. Check your connections in Settings and try again.')
    } catch (e) { setDestinationError(e.message) }
  }
  function useDestinations() {
    const cal = destinations?.calendars.find(c => c.id === calendarChoice)
    const page = destinations?.pages.find(p => p.notion_id === pageChoice)
    const selection = [cal && `Google calendar: ${cal.title} (calendar_id: ${cal.id}).`, page && `Notion page: ${page.file_name} (page_id: ${page.notion_id}).`].filter(Boolean).join(' ')
    setInput(v => `${v.trim()}${v.trim() ? '\n' : ''}For my earlier request, use these destinations: ${selection} Keep all the originally requested tasks and dates, and show the complete proposal for approval.`)
    setDestinationsOpen(false); inputRef.current?.focus()
  }
  async function history() {
    setLoading(true); setError('')
    try { const data = await api.get('/api/chat/history?session_id=default'); if (mounted.current) setMessages(data.messages || []) }
    catch (e) { if (mounted.current) setError(e.message) }
    finally { if (mounted.current) setLoading(false) }
  }
  useEffect(() => {
    let cancelled = false
    const refresh = () => api.get('/api/assistant/capabilities').then(data => { if (!cancelled) setCapabilities(data) }).catch(() => {})
    refresh()
    window.addEventListener('focus', refresh)
    window.addEventListener('vida:changed', refresh)
    return () => { cancelled = true; window.removeEventListener('focus', refresh); window.removeEventListener('vida:changed', refresh) }
  }, [visible])
  useEffect(() => { mounted.current = true; history(); return () => { mounted.current = false; recognition.current?.abort() } }, [])
  useEffect(() => { if (visible) inputRef.current?.focus(); else { recognition.current?.stop(); setListening(false) } }, [visible])
  useEffect(() => { scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' }) }, [messages, sending])
  const dictation = () => {
    if (listening) { recognition.current?.stop(); return }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) return
    const rec = new SR(); recognition.current = rec; rec.lang = 'en-US'; rec.interimResults = false
    rec.onresult = event => setInput(v => `${v}${v ? ' ' : ''}${event.results[0][0].transcript}`)
    rec.onerror = () => { setListening(false); setError('Microphone unavailable. You can keep typing.') }
    rec.onend = () => setListening(false)
    try { rec.start(); setListening(true) } catch { setError('Could not start dictation. Please try again.') }
  }
  async function send(text = input) {
    const message = text.trim()
    if (!message || sendingRef.current) return
    if (requests.some(r => ['pending','processing'].includes(r.status))) { setError('Your earlier request is still running. Its progress is shown below; wait for the review cards before sending again.'); return }
    sendingRef.current = true; setSending(true); setRequestStage('Waiting to start'); setInput(''); setError('')
    setMessages(v => [...v, { role: 'user', content: message }])
    try {
      const { job_id } = await api.post('/api/chat', { message, session_id: 'default', date: sessionStorage.getItem('vida_plan_date') || undefined })
      const job = await pollJob(job_id, {maxAttempts:50, onProgress:job => { if (mounted.current) setRequestStage(job.stage || 'Preparing your request') }})
      if (job.result?.plan) window.dispatchEvent(new Event('vida:changed'))
      if (!job.result?.reply) throw new Error('No answer was returned. Please try again.')
      if (mounted.current) setMessages(v => [...v, { role: 'assistant', content: job.result.reply, sources: job.result.sources || [], proposal: job.result.proposal, proposals: job.result.proposals || [] }])
    } catch (e) { if (mounted.current) { setError(e.message); setInput(message) } }
    finally { sendingRef.current = false; if (mounted.current) setSending(false) }
  }
  async function approve(proposal) {
    const steps = Array.isArray(proposal) ? proposal : [proposal]
    if (busyAction) return
    setBusyAction(steps[0]?.action_id); setError('')
    try {
      if (Array.isArray(proposal)) {
        await api.post('/api/workflows/approve', {action_ids: steps.map(p => p.action_id)})
        const activity = await api.get('/api/workflows'); setWorkflows(activity.workflows || [])
      } else for (const step of steps) {
        if (step.status !== 'pending') continue
        setBusyAction(step.action_id)
        const submitted = await api.post(`/api/actions/${encodeURIComponent(step.action_id)}/confirm`, {})
        if (submitted.job_id) await pollJob(submitted.job_id, {maxAttempts:60})
      }
      const data = await api.get('/api/chat/history?session_id=default')
      setMessages(data.messages || [])
      window.dispatchEvent(new Event('vida:changed'))
    } catch (e) {
      setError(e.message)
      try { const data=await api.get('/api/chat/history?session_id=default'); setMessages(data.messages || []) } catch {}
    }
    finally { setBusyAction(null) }
  }
  useEffect(() => {
    if (!visible) return
    let cancelled = false
    async function refreshActivity() {
      try {
        const data = await api.get('/api/workflows')
        if (cancelled) return
        setRequests(data.requests || []); setWorkflows(data.workflows || []); setNotices((data.notifications || []).sort((a,b) => b.created_at.localeCompare(a.created_at)).slice(0,3)); setActivityError('')
        const conversation = await api.get('/api/chat/history?session_id=default')
        if (!cancelled && !sendingRef.current) setMessages(conversation.messages || [])
      } catch { if (!cancelled) setActivityError('Background status is unavailable. Your work continues; reconnect to check results.') }
    }
    refreshActivity()
    const timer = setInterval(refreshActivity, 8000)
    return () => { cancelled = true; clearInterval(timer) }
  }, [visible])
  // Keep receipts in history, but show batch outcomes once in their step cards.
  let batchReceipts = []
  const displayMessages = []
  for (const message of messages) {
    if (message.role === 'user') batchReceipts = []
    if (message.proposals?.length) batchReceipts = message.proposals.filter(p => p.status === 'completed').map(p => p.result?.message).filter(Boolean)
    if (message.agent === 'executor') {
      const matched = batchReceipts.indexOf(message.content)
      if (matched !== -1) { batchReceipts.splice(matched, 1); continue }
      const previous = displayMessages[displayMessages.length - 1]
      if (previous?.receipts) previous.receipts.push(message)
      else displayMessages.push({ role: 'assistant', receipts: [message] })
    } else displayMessages.push(message)
  }
  async function fillDemo(label, prompt, starter = false) {
    if (preparingDemo || (starter && input.trim())) return
    setPreparingDemo(true)
    try {
      if (demo) prompt = prompt.replace(/GOOGLE CALENDAR/g, 'SAMPLE CALENDAR').replace('existing shared page “Vida demo test”', 'local sample page “Vida demo test” (page_id: demo-notion)').replace('existing shared Notion page named Vida demo test', 'local sample Notion page named Vida demo test (page_id: demo-notion)') + '\n\nTEST WORKSPACE: Use only local sample destinations: calendar_id demo-calendar and page_id demo-notion. Check the local sample schedule for availability. No external connection or sync is needed. All changes still require my approval. Label every integration result Demo only — not synced.'

      if (demo && label === 'Try organizing my Saturday') prompt = prompt.replace(/SAMPLE CALENDAR — one change[\s\S]*?REVIEW FIRST/, 'SAMPLE CALENDAR — one change\nPropose one calendar event titled “Walk and unwind” on {{SATURDAY}}, lasting 30 minutes in the earliest free slot between 5 PM and 8 PM. Use calendar_id demo-calendar and check the local sample schedule for conflicts. This is a sample event stored in Vida, not a web search or Google sync. Do not create a walk task.\n\nREVIEW FIRST')
      if (demo && label === 'Plan with my priorities') prompt = prompt.replace('synced Google Calendar', 'clearly labeled sample schedule')
      if (demo && label === 'Show my sources') prompt = prompt.replace('synced calendar commitments', 'sample schedule commitments')
      if (label === 'Try organizing my Saturday') {
        const data = await api.get('/api/profile')
        const timezone = data.profile?.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone
        prompt = prompt.replaceAll('{{SATURDAY}}', nextSaturday(timezone)).replaceAll('{{TIMEZONE}}', timezone)
      }
      if (starter && inputRef.current?.value.trim()) return
      setInput(prompt); inputRef.current?.focus()
      if (starter) dismissStarter()
    } catch { setError('Could not prepare the demo date. Please try again.') }
    finally { setPreparingDemo(false) }
  }
  const demoPrompts = [
    ['Try organizing my Saturday', "Help me get Saturday, {{SATURDAY}}, organized. Use {{TIMEZONE}} for all times. This exact date is the next upcoming Saturday, calculated by Vida; keep it for every step.\n\nTASKS — two changes\nCreate “Buy groceries”: 45 minutes, medium priority, due that Saturday.\nCreate “Do laundry”: 30 minutes, medium priority, due that Saturday.\nKeep both unassigned to a project. If an exact matching task already exists for that date, show it instead of creating a duplicate.\n\nSHOPPING LIST — one change\nSave a Library note titled “Saturday groceries — {{SATURDAY}}”. Text: “Eggs, milk, rice, spinach, and bananas.”\n\nNOTION CHECKLIST — one change\nAppend this text to the existing shared page “Vida demo test”, keeping its current contents: “Saturday reset: buy groceries, do laundry, and take a 30-minute walk.” Verify a unique matching page in the current catalog. If it is missing or ambiguous, list available pages for me to choose; keep the other proposals ready.\n\nGOOGLE CALENDAR — one change\nFind the earliest free 30-minute slot that Saturday between 5 PM and 8 PM in my saved timezone. Propose an event titled “Walk and unwind”. Use my only selected writable calendar; if there are several, list their names so I can choose. Check conflicts across my selected calendars and verify that the synced data covers that date. If you cannot verify availability or no slot fits, keep this step blocked and ask me what to change. Do not create a separate walk task.\n\nREVIEW FIRST\nShow all five steps together, including any blocked steps. Explain the date, destinations, and any assumptions. Do not save tasks or notes, edit Notion, or book an event until I approve the corresponding proposal."],
    ['Show my sources', 'Give me a short overview of my saved notes, open tasks, and synced calendar commitments for today and tomorrow in my saved timezone. Cite the notes you use and separate saved facts from suggestions. Default: show the three most relevant notes and up to five tasks or events. If something is missing or the calendar does not cover those dates, say what is missing and show what you can. Do not change anything.'],
    ['Plan with my priorities', 'Help me plan tomorrow around my synced Google Calendar, using my saved timezone and planning hours. If I already have saved focus tasks, use those to create a draft. Otherwise, recommend up to three of my existing open tasks: overdue first, then nearest due date, then shorter tasks that fit. Show the task names, durations, and your reasons in a priority-choice proposal for my approval before saving. Do not create new tasks. If no tasks exist, tell me to add one in Projects. After I approve the priorities, guide me to generate the draft in Plan. Explain what fits and what must wait; do not apply the draft or book calendar events automatically.'],
    ['Update a Notion page', 'Append this exact checklist to the existing shared Notion page named Vida demo test, preserving everything already there: “Saturday reset: buy groceries, do laundry, and take a 30-minute walk.” Use a case-insensitive exact title match from the current page catalog. If there is no unique match, list up to five actual shared pages for me to choose from; do not create a page or guess its ID. Show the page title and exact text in an approval card before writing. If this exact checklist already exists, tell me rather than appending it again.'],
    ['Schedule focus time', 'Find a free 30-minute slot tomorrow between 5 PM and 8 PM in my saved timezone for an event titled Focus time. Default: choose the earliest available slot and use my only selected writable Google calendar. If several calendars are selected, list their names so I can choose; do not guess. Check all selected calendars for conflicts and verify that tomorrow is within the synced coverage. If availability cannot be verified or no slot fits, explain that and ask for another date or time window. Show the exact calendar, date, time, and timezone for approval before creating the event. Do not create a separate task.'],
    ['Research with sources', 'Prepare a public web search for “Amazon Bedrock announcements last 30 days”. Show the exact query as an approval card before searching; do not include my private notes or personal data. After approval, summarize up to three relevant findings with source links and publication dates, favor official AWS sources, and explain one practical use for each. If there are no reliable recent results, say so. Do not save notes, create tasks, or change my plan unless I separately request and approve those changes.'],
  ]
  const promptButtons = <div className="suggestion-grid">{demoPrompts.map(([label,prompt]) => <button key={label} disabled={sending || preparingDemo || (label === 'Research with sources' && !capabilities.web_search)} title={label === 'Research with sources' && !capabilities.web_search ? 'Add a Tavily key to enable web research' : prompt} onClick={() => fillDemo(label, prompt)}>{label}</button>)}</div>
  return <div className="assistant-panel">
    <header className="assistant-header"><span className="assistant-symbol"><Sparkles size={21} /></span><div><h2>Ask Vida</h2><p>Your plans, tasks & knowledge</p></div><button onClick={onClose} className="icon-button" aria-label="Close chat"><X size={20} /></button></header>
    <div className="assistant-scope"><FileText size={15} /> Sources → Preview → Your approval → Result</div>
    {(demo || (capabilities.google_calendar && capabilities.notion)) && !starterDismissed && <section className="m-3 p-4 rounded-xl border border-vida-200 bg-vida-50" aria-label="Saturday starter">
      <p className="text-xs font-semibold text-vida-700">{demo ? 'TRY FIVE LOCAL CHANGES · NOTHING SYNCED' : 'YOUR TOOLS ARE CONNECTED'}</p>
      <h3 className="font-semibold mt-1">Get my Saturday together</h3>
      <p className="text-sm mt-2">Try groceries, laundry, a shopping list, a Notion checklist, and a walk. We’ll fill in the date and defaults; you review every change.</p>
      <div className="flex gap-3 mt-3"><button className="approve-action" disabled={sending || preparingDemo || !!input.trim()} onClick={() => fillDemo(...demoPrompts[0], true)}>{preparingDemo ? 'Preparing…' : 'Try organizing my Saturday'}</button><button className="text-sm underline" onClick={dismissStarter}>Not now</button></div>
      {input.trim() && <p className="text-xs mt-2">Your draft is safe. Send or clear it before loading the starter.</p>}
      <p className="text-xs mt-2">Loads a draft only. Nothing is sent or changed automatically.</p>
    </section>}
    <div className="assistant-messages" ref={scrollRef} aria-live="polite" aria-relevant="additions text">
      {loading && <div className="assistant-loading"><Loader2 size={18} className="animate-spin" /> Loading conversation</div>}
      {!loading && messages.length === 0 && <div className="assistant-welcome"><span className="welcome-eyebrow">{demo ? 'ISOLATED SAMPLE WORKSPACE' : 'YOUR WORKSPACE, CONNECTED'}</span><h3>Turn context into a clear next step.</h3><p>Find evidence in your notes, organize tasks, and preview changes to Notion or Google Calendar.</p>{promptButtons}<p className="text-xs mt-3">{demo ? 'Real integrations disabled in test mode' : capabilities.notion ? 'Notion connected' : 'Connect Notion in Settings'} · {demo ? 'Sample schedule' : capabilities.google_calendar ? 'Calendar connected' : 'Connect Calendar in Settings'} · {capabilities.web_search ? 'Web research enabled' : 'Web research needs a search key'}</p></div>}
      {!loading && messages.length > 0 && <details className="p-3 border rounded-lg mb-3"><summary className="text-sm cursor-pointer">Try a demo prompt</summary><p className="text-xs text-gray-500 my-2">Choose a starting point. Defaults are included—edit the message before sending. Changes still need your approval.</p>{promptButtons}</details>}
      {displayMessages.map((m, i) => m.receipts ? <article key={i} className="chat-message receipt-group"><span className="message-label">Completed changes</span><ul>{m.receipts.map((r,n) => <li key={n}><Check size={14} aria-hidden="true" /><span>{r.content} <ResultLink url={r.result_url} /></span></li>)}</ul></article> : <article key={i} className={`chat-message ${m.role}`}><span className="message-label">{m.role === 'user' ? 'You' : 'Vida'}</span><div className="message-body">{m.proposals?.length && m.proposals.every(p => p.status === 'completed') ? 'Your approved changes are saved. Open a result below or expand the details.' : m.content}</div><ResultLink url={m.result_url} />
        {m.sources?.length > 0 && <div className="source-list"><button onClick={() => setSourcesOpen(sourcesOpen === i ? null : i)} className="source-toggle" aria-expanded={sourcesOpen === i}><FileText size={14} />{m.sources.length} sources<ChevronDown size={14} /></button>{sourcesOpen === i && m.sources.map(s => <details key={s.id}><summary>[{s.id}] {s.title}</summary><p>{s.passage}</p>{s.published_date && <p>Published: {s.published_date}</p>}{s.retrieved_at && <p>Retrieved: {new Date(s.retrieved_at).toLocaleString()}</p>}{s.url?.startsWith('https://') && <a href={s.url} target="_blank" rel="noopener noreferrer">Open source</a>}</details>)}</div>}
        {(m.proposals?.length > 0 || m.proposal) && <div className="space-y-3">
          {m.proposals?.length > 1 && <div className="action-card"><strong>{m.proposals.every(p => p.status === 'completed') ? `${m.proposals.length} changes completed` : `${m.proposals.length} requested changes`}</strong><p>{m.proposals.every(p => p.status === 'completed') ? (demo ? 'Saved in this demo workspace only. Nothing synced to personal accounts.' : 'Each result is saved below. Completed steps are not repeated.') : 'Review each change before approving. Ready steps run in the background; completed steps are not repeated.'}</p>{m.proposals.every(p => p.status === 'completed') && <div className="flex flex-wrap gap-2 mt-2"><a className="result-button" href="/projects">View tasks</a><a className="result-button" href="/library">View notes</a><a className="result-button" href={'/plan?date='+(m.proposals.find(p => p.action?.action === 'create_event')?.action?.date || '')}>View schedule</a></div>}<button hidden={m.proposals.every(p => p.status === 'completed')} className="approve-action" disabled={!!busyAction || !m.proposals.some(p => p.status === 'pending')} onClick={() => approve(m.proposals.filter(p => p.status === 'pending'))}>Approve all ready steps</button></div>}
          <details open={!(m.proposals?.length ? m.proposals : [m.proposal]).every(p => p.status === 'completed')}><summary className="text-sm cursor-pointer mt-2">Change details and results</summary>
          {(m.proposals?.length ? m.proposals : [m.proposal]).map((p, n) => <div key={p.action_id || n} className={`action-card action-${p.status}`}><span className="action-eyebrow">{p.status === 'completed' ? 'COMPLETED' : p.status === 'blocked' ? (demoRestricted(p) ? 'PERSONAL WORKSPACE REQUIRED' : 'NEEDS CLARIFICATION') : p.status === 'needs_review' ? 'CHECK DESTINATION' : p.status === 'processing' ? 'APPLYING' : 'REVIEW BEFORE APPLYING'}</span><strong>{m.proposals?.length ? `${n + 1}. ` : ''}{labels[p.action?.action] || 'Review change'}</strong><dl>{Object.entries(p.action || {}).filter(([k,v]) => !['action','page_id','event_id','page_url'].includes(k) && !k.startsWith('_') && v != null && v !== '').map(([k,v]) => <div key={k}><dt>{k.replaceAll('_',' ')}</dt><dd>{typeof v === 'object' ? JSON.stringify(v, null, 2) : String(v)}</dd></div>)}</dl>{p.error && <p role="alert">{demoRestricted(p) ? "Test mode cannot read or change a real Google Calendar or Notion page. Use Start clean & connect my accounts; no sample data will carry over." : p.error}</p>}{p.result && <div className="action-result"><span>{p.result.message}</span><ResultLink url={p.result.url} /></div>}<button disabled={!!busyAction || p.status !== 'pending'} onClick={() => approve(p)} className="approve-action">{busyAction === p.action_id ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}{p.status === 'completed' ? 'Completed' : p.status === 'pending' ? 'Approve & run' : p.status === 'blocked' ? (demoRestricted(p) ? 'Use “Start clean & connect my accounts” above' : 'Clarify in chat') : 'Check destination'}</button></div>)}
          </details>
        </div>}
      </article>)}
      {sending && <div className="assistant-loading" role="status"><Loader2 size={18} className="animate-spin" /> {requestStage} — changes still need your approval.</div>}
    </div>
    {!sending && requests.map(r => <div key={r.job_id} role="status" className="p-3 border-t text-sm"><strong>{r.status === 'failed' ? 'Request interrupted' : 'Request in progress'}</strong><p>{r.status === 'failed' ? r.error : r.stage}</p></div>)}
    {workflows.length > 0 && <details className="p-3 border-t text-sm" open={workflows.some(w => w.status === 'running')}><summary>Approved changes · {workflows.some(w => w.status === 'running') ? 'In progress' : 'Previous results'}</summary>{workflows.slice(0,3).map(w => <div key={w.workflow_id} className="mt-2" role="status"><strong>{w.completed}/{w.total} completed</strong> · {w.status === 'running' ? 'Working in the background' : w.status === 'completed' ? 'All approved steps finished' : 'Some steps need review'}{w.steps.filter(s => s.status === 'needs_review').map(s => <p key={s.action_id}>{s.result?.message || 'Check the destination before retrying.'}</p>)}</div>)}{notices.map(n => <p key={n.workflow_id + n.action_id + n.status} className="text-xs mt-1">{n.message}</p>)}</details>}
    {activityError && <p className="text-xs p-2" role="status">{activityError}</p>}
    {error && <div className="chat-error" role="alert">{error}{!messages.length && <button onClick={history}><RotateCcw size={14} />Retry</button>}</div>}
    <div className="border-t px-4 py-2 text-sm">
      <button type="button" className="text-vida-700 underline" aria-expanded={destinationsOpen} onClick={() => destinationsOpen ? setDestinationsOpen(false) : loadDestinations()}>Choose calendar / Notion page</button>
      {destinationsOpen && <div className="space-y-2 mt-2 max-h-64 overflow-auto">
        {!destinations && !destinationError && <p role="status">Loading your connected options…</p>}
        {destinationError && <p role="alert">{destinationError}</p>}
        {destinations && <>
          <label className="block">Google Calendar<select aria-label="Google Calendar destination" className="block border rounded p-2 w-full" value={calendarChoice} onChange={e => setCalendarChoice(e.target.value)}><option value="">Choose a calendar</option>{destinations.calendars.map(c => <option key={c.id} value={c.id} disabled={!['owner','writer'].includes(c.access_role)}>{c.title}{c.primary ? ' (primary)' : ''}{!['owner','writer'].includes(c.access_role) ? ' — read only' : ''}</option>)}</select></label>
          {!destinations.calendars.length && <p>No selected calendars. Connect and choose calendars in Settings.</p>}
          <label className="block">Notion page<select aria-label="Notion page destination" className="block border rounded p-2 w-full" value={pageChoice} onChange={e => setPageChoice(e.target.value)}><option value="">Choose a shared page</option>{destinations.pages.map(p => <option key={p.notion_id} value={p.notion_id}>{p.file_name} · {p.notion_id.slice(-6)}</option>)}</select></label>
          {!destinations.pages.length && <p>No synced Notion pages. Share the page with Vida and sync in Settings.</p>}
          <p className="text-xs text-gray-500">Adds your choice to the message. Nothing is changed or sent yet.</p>
          <button type="button" disabled={!calendarChoice && !pageChoice} onClick={useDestinations} className="px-3 py-2 bg-vida-600 text-white rounded disabled:opacity-50">Use selected destinations</button>
        </>}
        <a href="/settings" className="block text-vida-700 underline">Manage connections in Settings</a>
      </div>}
    </div>
    <form className="assistant-composer" onSubmit={e => { e.preventDefault(); send() }}><label htmlFor="vida-message" className="sr-only">Message Vida</label><textarea id="vida-message" ref={inputRef} value={input} onChange={e => setInput(e.target.value)} maxLength={8000} rows={3} placeholder="Ask a question or describe a task…" onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send() } }} /><div className="composer-tools"><span>{listening ? 'Listening…' : 'Changes need your approval'}</span>{speechAvailable && <button type="button" className={`icon-button ${listening ? 'recording' : ''}`} aria-label={listening ? 'Stop dictation' : 'Dictate message'} aria-pressed={listening} onClick={dictation}>{listening ? <MicOff size={19} /> : <Mic size={19} />}</button>}<button className="send-button" disabled={!input.trim() || sending || loading} aria-label="Send message">{sending ? <Loader2 className="animate-spin" size={18} /> : <Send size={18} />}</button></div></form>
    <p className="assistant-footnote">Check sources and proposed changes before relying on AI.</p>
  </div>
}
