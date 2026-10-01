import { NavLink } from 'react-router-dom'
import { Sun, Calendar, BarChart3, BookOpen } from 'lucide-react'

const navItems = [
  { to: '/today', label: 'Today', icon: Sun },
  { to: '/plan', label: 'Plan', icon: Calendar },
  { to: '/progress', label: 'Progress', icon: BarChart3 },
  { to: '/library', label: 'Library', icon: BookOpen },
]

export default function Sidebar({ profile }) {
  return (
    <aside className="fixed left-0 top-0 w-64 h-screen bg-white border-r border-gray-200 flex flex-col">
      <div className="p-6 border-b border-gray-100">
        <h1 className="text-2xl font-bold text-vida-600">Vida</h1>
        <p className="text-sm text-gray-500 mt-1">AI Life Assistant</p>
      </div>

      <nav className="flex-1 p-4 space-y-1">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-vida-50 text-vida-700'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              }`
            }
          >
            <Icon size={20} />
            {label}
          </NavLink>
        ))}
      </nav>

      {profile && (
        <div className="p-4 border-t border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-vida-100 text-vida-700 rounded-full flex items-center justify-center text-sm font-semibold">
              {(profile.name || 'U')[0].toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-gray-900 truncate">{profile.name || 'User'}</div>
              <div className="text-xs text-gray-500 truncate">{profile.role || profile.phase}</div>
            </div>
          </div>
        </div>
      )}
    </aside>
  )
}
