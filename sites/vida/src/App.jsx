import { useState, useEffect } from 'react'
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { getSession, createSession, api } from './lib/api'
import CalendarGate from './components/layout/CalendarGate'
import AppShell from './components/layout/AppShell'
import ProjectsPage from './pages/ProjectsPage'
import TodayPage from './pages/TodayPage'
import PlanPage from './pages/PlanPage'
import ProgressPage from './pages/ProgressPage'
import LibraryPage from './pages/LibraryPage'
import SettingsPage from './pages/SettingsPage'
import OnboardingPage from './pages/OnboardingPage'

export default function App() {
  const [session, setSession] = useState(getSession())
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    async function init() {
      try {
      let s = getSession()
      if (!s) {
        s = await createSession()
      }
      setSession(s)

      try {
        const data = await api.get('/api/profile')
        if (data.profile && !data.profile.timezone) {
          const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
          const updated = await api.put('/api/profile', { timezone })
          data.profile = updated.profile
        }
        setProfile(data.profile)
        if (!data.profile?.onboarded && window.location.pathname !== '/test') {
          navigate('/onboard')
        }
      } catch (err) { throw err }
      setLoading(false)
      } catch (e) { setError(e.message); setLoading(false) }
    }
    init()
  }, [])

  const handleOnboardComplete = (p) => {
    setProfile(p)
    setSession(getSession())
    navigate(p?.sample_data ? '/today' : '/settings')
  }

  if (error) return <div className="min-h-screen grid place-items-center p-6"><div role="alert"><h1 className="text-2xl font-bold mb-3">Could not connect to Vida</h1><p>{error}</p><button className="mt-4 text-vida-600 underline" onClick={() => window.location.reload()}>Try again</button></div></div>

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="text-4xl font-bold text-vida-600 mb-2">Vida</div>
          <div className="text-gray-500">Loading your assistant...</div>
        </div>
      </div>
    )
  }

  return (
    <Routes>
      <Route path="/test" element={<OnboardingPage testOnly onComplete={handleOnboardComplete} />} />
      <Route path="/onboard" element={<OnboardingPage onComplete={handleOnboardComplete} />} />
      <Route element={<AppShell profile={profile} />}>
        <Route element={<CalendarGate demo={!!profile?.sample_data} />}>
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/today" element={<TodayPage demo={!!profile?.sample_data} />} />
        <Route path="/plan" element={<PlanPage />} />
        <Route path="/progress" element={<ProgressPage />} />
        <Route path="/library" element={<LibraryPage />} />
        </Route>
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/" element={<Navigate to="/today" replace />} />
      </Route>
    </Routes>
  )
}
