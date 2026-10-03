import { NavLink } from 'react-router-dom'
import { FolderOpen, Sun, CalendarDays, TrendingUp, BookOpen, Settings, X } from 'lucide-react'
const items = [ ['/today', 'Today', Sun], ['/projects', 'Projects', FolderOpen], ['/plan', 'Plan', CalendarDays], ['/progress', 'Progress', TrendingUp], ['/library', 'Library', BookOpen] ]
export default function Sidebar({ profile, open, onClose }) {
  return <aside className={`vida-sidebar ${open ? 'is-open' : ''}`}>
    <div className="brand"><span className="brand-mark">v</span><span>vida<span className="brand-dot">.</span></span><button className="icon-button mobile-menu" onClick={onClose} aria-label="Close navigation"><X size={20} /></button></div>
    <div className="nav-caption">YOUR SPACE</div>
    <nav aria-label="Main navigation">{items.map(([to, label, Icon]) => <NavLink key={to} to={to} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}><Icon size={20} />{label}</NavLink>)}</nav>
    <div className="sidebar-bottom"><NavLink to="/settings" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}><Settings size={20} />Settings</NavLink>
      <div className="profile-chip"><span className="avatar">{(profile?.name || 'You')[0].toUpperCase()}</span><div><strong>{profile?.name || 'Your workspace'}</strong><span>{profile?.role || 'One day at a time'}</span></div></div>
    </div>
  </aside>
}
