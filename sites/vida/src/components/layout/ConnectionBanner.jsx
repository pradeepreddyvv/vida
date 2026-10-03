import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { api } from '../../lib/api'

export default function ConnectionBanner() {
  const [connections, setConnections] = useState(null)
  const [error, setError] = useState(false)
  const location = useLocation()
  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const result = await api.get('/api/integrations')
        if (active) { setConnections(result.integrations || []); setError(false) }
      } catch { if (active) setError(true) }
    }
    load()
    window.addEventListener('vida:changed', load)
    window.addEventListener('focus', load)
    return () => { active = false; window.removeEventListener('vida:changed', load); window.removeEventListener('focus', load) }
  }, [location.pathname, location.search])
  if (error) return <section className="connection-banner" aria-label="Connection setup"><span>Couldn’t check your connections.</span><Link to="/settings#integrations">Check Settings →</Link></section>
  if (!connections) return null
  const connected = provider => connections.some(i => i.provider === provider && i.status === 'connected')
  const google = connected('google_calendar'), notion = connected('notion')
  if (google && notion) return null
  return <section className="connection-banner" aria-label="Finish setting up Vida">
    <div><strong>Bring your day together</strong><p>Connect your tools once. Vida can use your real schedule and keep your tasks and habits in Notion.</p></div>
    <div className="connection-banner-actions">
      {!google && <Link to="/settings#google-calendar">Connect Google Calendar <small>Required for planning</small></Link>}
      {!notion && <Link to="/settings#notion">Connect Notion <small>Required to explore</small></Link>}
    </div>
  </section>
}
