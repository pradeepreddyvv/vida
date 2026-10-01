import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import ChatPanel from '../chat/ChatPanel'
import { MessageCircle, X } from 'lucide-react'

export default function AppShell({ profile }) {
  const [chatOpen, setChatOpen] = useState(false)

  return (
    <div className="min-h-screen flex bg-gray-50">
      <Sidebar profile={profile} />

      <main className="flex-1 ml-64 p-6 overflow-auto">
        <Outlet />
      </main>

      <button
        onClick={() => setChatOpen(!chatOpen)}
        className="fixed bottom-6 right-6 w-14 h-14 bg-vida-600 text-white rounded-full shadow-lg flex items-center justify-center hover:bg-vida-700 transition-colors z-40"
      >
        {chatOpen ? <X size={24} /> : <MessageCircle size={24} />}
      </button>

      {chatOpen && (
        <div className="fixed bottom-24 right-6 w-96 h-[500px] bg-white rounded-xl shadow-2xl border z-50 flex flex-col">
          <ChatPanel onClose={() => setChatOpen(false)} />
        </div>
      )}
    </div>
  )
}
