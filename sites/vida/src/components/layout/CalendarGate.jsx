import { useEffect, useState } from 'react'
import { Link, Outlet } from 'react-router-dom'
import { api } from '../../lib/api'

export default function CalendarGate({ demo = false }) {
  const [state, setState] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let live = true
    const load = () => api.get('/api/integrations').then(data => {
      if (live) { setState({...(data.integrations.find(i => i.provider === 'google_calendar') || {}), notionConnected:data.integrations.some(i => i.provider === 'notion' && i.status === 'connected')}); setError('') }
    }).catch(e => { if(live) setError(e.message) })
    load(); window.addEventListener('vida:changed', load)
    return () => { live = false; window.removeEventListener('vida:changed', load) }
  }, [])
  if (demo) return <Outlet />
  if (error) return <div role="alert">{error} <Link to="/settings" className="underline">Open Settings</Link></div>
  if (!state) return <p role="status">Checking your calendar connection…</p>
  if (state.status !== 'connected' || !state.selected_calendars?.length || state.sync_status !== 'complete' || !state.notionConnected) return <section className="max-w-xl bg-white border rounded-xl p-6 space-y-4"><h1 className="text-2xl font-semibold">Connect your tools first</h1><p>Connect Google Calendar and Notion before exploring your workspace. Select your calendars and finish the calendar sync. Each visitor connects their own accounts.</p><Link to="/settings" className="inline-block bg-vida-600 text-white px-4 py-2 rounded-lg">Connect Google Calendar & Notion</Link></section>
  return <Outlet />
}
