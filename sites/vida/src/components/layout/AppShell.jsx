import { useEffect, useRef, useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { MessageSquare, PanelRightClose, Menu, GripVertical } from 'lucide-react'
import Sidebar from './Sidebar'
import ConnectionBanner from './ConnectionBanner'
import ChatPanel from '../chat/ChatPanel'
import { createSession } from '../../lib/api'

export default function AppShell({ profile }) {
  const [leavingDemo, setLeavingDemo] = useState(false)
  const [demoError, setDemoError] = useState('')
  async function startPersonal() {
    setLeavingDemo(true); setDemoError('')
    try { await createSession(); window.location.assign('/onboard') }
    catch (e) { setDemoError(e.message); setLeavingDemo(false) }
  }
  const [chatOpen, setChatOpen] = useState(() => window.innerWidth >= 1100)
  const [navOpen, setNavOpen] = useState(false)
  const [width, setWidth] = useState(() => Math.min(640, Math.max(380, Number(localStorage.getItem('vida_chat_width')) || 480)))
  const [refresh, setRefresh] = useState(0)
  const handle = useRef(null)
  const location = useLocation()
  const navigate = useNavigate()
  useEffect(() => {
    if (!document.modelContext?.registerTool) return
    const lifecycle = new AbortController()
    const routes = ['today', 'projects', 'plan', 'progress', 'library', 'settings']
    try {
      Promise.resolve(document.modelContext.registerTool({
        name: 'navigate_vida', title: 'Open a Vida page',
        description: 'Open Today, Projects, Plan, Progress, Library, or Settings. Does not change saved data.',
        inputSchema: { type: 'object', properties: { page: { type: 'string', enum: routes } }, required: ['page'], additionalProperties: false },
        annotations: { readOnlyHint: false, untrustedContentHint: false },
        async execute(input) {
          if (!input || !routes.includes(input.page) || Object.keys(input).some(k => k !== 'page')) throw new Error('Choose a valid Vida page')
          navigate('/' + input.page)
          await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))
          return { page: input.page }
        }
      }, { signal: lifecycle.signal })).catch(() => {})
    } catch { /* Optional browser capability. */ }
    return () => lifecycle.abort()
  }, [navigate])
  useEffect(() => { setNavOpen(false) }, [location.pathname])
  useEffect(() => {
    const key = e => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); setChatOpen(v => !v) }
      if (e.key === 'Escape') { setNavOpen(false); setChatOpen(false) }
    }
    const changed = () => setRefresh(v => v + 1)
    window.addEventListener('keydown', key)
    window.addEventListener('vida:changed', changed)
    return () => { window.removeEventListener('keydown', key); window.removeEventListener('vida:changed', changed) }
  }, [])
  const resize = next => {
    const value = Math.max(360, Math.min(720, window.innerWidth - 480, next))
    setWidth(value); localStorage.setItem('vida_chat_width', value)
  }
  return (
    <div className={`vida-workspace ${chatOpen ? 'chat-open' : ''}`} style={{ '--chat-width': `${width}px` }}>
      <Sidebar profile={profile} open={navOpen} onClose={() => setNavOpen(false)} />
      {navOpen && <button className="nav-scrim" aria-label="Close navigation" onClick={() => setNavOpen(false)} />}
      <div className="workspace-main">
        <header className="workspace-toolbar">
          <button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setNavOpen(true)}><Menu size={20} /></button>
          <span className="workspace-breadcrumb">Workspace <span>/</span> <strong>{location.pathname.slice(1) || 'Today'}</strong></span>
          <button className="chat-toggle" aria-expanded={chatOpen} aria-controls="vida-chat" onClick={() => setChatOpen(v => !v)}>
            {chatOpen ? <PanelRightClose size={18} /> : <MessageSquare size={18} />} <span>{chatOpen ? 'Hide chat' : 'Ask Vida'}</span><kbd>⌘ K</kbd>
          </button>
        </header>
        {profile?.sample_data ? <div className="p-3 bg-amber-50 border-b text-sm"><strong>Test workspace · {profile.name}</strong><p>Fictional data. Approved Calendar and Notion changes complete here only—never synced. Start clean before connecting real accounts; no sample data carries over.</p><button className="underline font-semibold mt-2" disabled={leavingDemo} onClick={startPersonal}>{leavingDemo ? 'Starting clean…' : 'Start clean & connect my accounts'}</button>{demoError && <p role="alert">{demoError}</p>}</div> : <ConnectionBanner />}
        <main className="workspace-content" key={refresh}><Outlet /></main>
      </div>
      <aside id="vida-chat" className="workspace-chat" hidden={!chatOpen} aria-label="Vida assistant">
        <div ref={handle} className="chat-resizer" role="separator" tabIndex={0} aria-label="Resize chat" aria-orientation="vertical" aria-valuemin={360} aria-valuemax={720} aria-valuenow={width}
          onKeyDown={e => { if (['ArrowLeft', 'ArrowRight'].includes(e.key)) { e.preventDefault(); resize(width + (e.key === 'ArrowLeft' ? 20 : -20)) } }}
          onPointerDown={e => { e.currentTarget.setPointerCapture(e.pointerId) }}
          onPointerMove={e => { if (e.currentTarget.hasPointerCapture(e.pointerId)) resize(window.innerWidth - e.clientX) }}
          onPointerUp={e => { if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId) }}><GripVertical size={14} /></div>
        <ChatPanel demo={!!profile?.sample_data} onClose={() => setChatOpen(false)} visible={chatOpen} />
      </aside>
    </div>
  )
}
