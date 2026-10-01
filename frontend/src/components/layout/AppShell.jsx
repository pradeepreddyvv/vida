import { useState, useEffect } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import ChatPanel from '../chat/ChatPanel'
import { MessageCircle, X } from 'lucide-react'

export default function AppShell({ profile }) {
  const [chatOpen, setChatOpen] = useState(false)

  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setChatOpen(prev => !prev)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  return (
    <div className="min-h-screen flex bg-gray-50">
      <Sidebar profile={profile} />

      <main className="flex-1 ml-64 p-6 overflow-auto">
        <Outlet />
      </main>

      <div className="fixed bottom-6 right-6 z-40 group">
        <button
          onClick={() => setChatOpen(!chatOpen)}
          className="w-14 h-14 bg-vida-600 text-white rounded-full shadow-lg flex items-center justify-center hover:bg-vida-700 transition-colors hover:scale-105"
        >
          {chatOpen ? <X size={24} /> : <MessageCircle size={24} />}
        </button>
        {!chatOpen && (
          <span className="absolute bottom-full right-0 mb-2 px-2.5 py-1 text-xs text-white bg-gray-800 rounded-lg whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
            Ask Vida <kbd className="ml-1 px-1 py-0.5 bg-gray-600 rounded text-[10px]">{navigator.platform?.includes('Mac') ? '⌘' : 'Ctrl'}K</kbd>
          </span>
        )}
      </div>

      {chatOpen && (
        <div className="fixed bottom-24 right-6 w-[420px] h-[560px] bg-white rounded-xl shadow-2xl border z-50 flex flex-col">
          <ChatPanel onClose={() => setChatOpen(false)} />
        </div>
      )}
    </div>
  )
}
