import { useState, useEffect, useRef } from 'react'
import { X, Send, Loader2, Sparkles } from 'lucide-react'
import { api, pollJob } from '../../lib/api'

export default function ChatPanel({ onClose }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [loading, setLoading] = useState(true)
  const scrollRef = useRef(null)

  useEffect(() => {
    async function loadHistory() {
      try {
        const data = await api.get('/api/chat/history?session_id=default')
        setMessages((data.messages || []).map(m => ({
          role: m.role,
          content: m.content,
          timestamp: m.timestamp,
        })))
      } catch { /* first time, no history */ }
      setLoading(false)
    }
    loadHistory()
  }, [])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, sending])

  const handleSend = async () => {
    const text = input.trim()
    if (!text || sending) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: text, timestamp: new Date().toISOString() }])
    setSending(true)
    try {
      const { job_id } = await api.post('/api/chat', { message: text, session_id: 'default' })
      const result = await pollJob(job_id)
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: result.result?.reply || 'Sorry, I could not generate a response.',
        timestamp: new Date().toISOString(),
      }])
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Something went wrong. Please try again.',
        timestamp: new Date().toISOString(),
      }])
    } finally {
      setSending(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const formatTime = (ts) => {
    if (!ts) return ''
    try {
      return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    } catch { return '' }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b bg-vida-50 rounded-t-xl">
        <div className="flex items-center gap-2">
          <Sparkles size={18} className="text-vida-600" />
          <span className="font-semibold text-vida-700 text-sm">Ask Vida</span>
        </div>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
          <X size={18} />
        </button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {loading && (
          <div className="flex justify-center py-8">
            <Loader2 size={24} className="animate-spin text-gray-400" />
          </div>
        )}

        {!loading && messages.length === 0 && (
          <div className="text-center py-8 text-sm text-gray-400">
            <Sparkles size={32} className="mx-auto mb-2 text-vida-300" />
            <p>Ask Vida anything about your goals, schedule, or tasks.</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] px-3.5 py-2 rounded-2xl text-sm leading-relaxed ${
              msg.role === 'user'
                ? 'bg-vida-600 text-white rounded-br-md'
                : 'bg-gray-100 text-gray-800 rounded-bl-md'
            }`}>
              <p className="whitespace-pre-wrap">{msg.content}</p>
              <div className={`text-[10px] mt-1 ${
                msg.role === 'user' ? 'text-vida-200' : 'text-gray-400'
              }`}>
                {formatTime(msg.timestamp)}
              </div>
            </div>
          </div>
        ))}

        {sending && (
          <div className="flex justify-start">
            <div className="bg-gray-100 px-4 py-3 rounded-2xl rounded-bl-md">
              <div className="flex gap-1.5">
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t px-3 py-2">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask Vida..."
            rows={1}
            className="flex-1 resize-none px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-vida-500 focus:border-vida-500 outline-none max-h-24"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || sending}
            className="p-2 bg-vida-600 text-white rounded-lg hover:bg-vida-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex-shrink-0"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}
