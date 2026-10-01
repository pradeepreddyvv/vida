import { useState, useEffect } from 'react'
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { getSession, createSession, api } from './lib/api'
import AppShell from './components/layout/AppShell'
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
  const navigate = useNavigate()

  useEffect(() => {
    async function init() {
      let s = getSession()
      if (!s) {
        s = await createSession()
      }
      setSession(s)

      try {
        const data = await api.get('/api/profile')
        setProfile(data.profile)
        if (!data.profile?.onboarded) {
          navigate('/onboard')
        }
      } catch {
        navigate('/onboard')
      }
      setLoading(false)
    }
    init()
  }, [])

  const handleOnboardComplete = (p) => {
    setProfile(p)
    navigate('/today')
  }

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
      <Route path="/onboard" element={<OnboardingPage onComplete={handleOnboardComplete} />} />
      <Route element={<AppShell profile={profile} />}>
        <Route path="/today" element={<TodayPage />} />
        <Route path="/plan" element={<PlanPage />} />
        <Route path="/progress" element={<ProgressPage />} />
        <Route path="/library" element={<LibraryPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/" element={<Navigate to="/today" replace />} />
      </Route>
    </Routes>
  )
}
