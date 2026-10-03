import { useState, useEffect, useRef, useCallback } from 'react'
import { X, Send, Loader2, Sparkles, Mic, MicOff, Volume2, VolumeX } from 'lucide-react'
import { api, pollJob } from '../../lib/api'

const QUICK_ACTIONS = ['Plan my day', "What's next?", 'Weekly review', 'Summarize my goals']

export default function ChatPanel({ onClose }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [loading, setLoading] = useState(true)
  const [isListening, setIsListening] = useState(false)
  const [speechSupported, setSpeechSupported] = useState(false)
  const [speaking, setSpeaking] = useState(null)
  const [autoSpeak, setAutoSpeak] = useState(false)
  const scrollRef = useRef(null)
  const recognitionRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (SR) {
      setSpeechSupported(true)
      const recognition = new SR()
      recognition.continuous = false
      recognition.interimResults = true
      recognition.lang = 'en-US'
      recognition.onresult = (event) => {
        const transcript = Array.from(event.results)
          .map(r => r[0].transcript)
          .join('')
        if (event.results[0].isFinal) {
          setInput(prev => prev + (prev ? ' ' : '') + transcript)
          setIsListening(false)
        }
      }
      recognition.onerror = () => setIsListening(false)
      recognition.onend = () => setIsListening(false)
      recognitionRef.current = recognition
    }
  }, [])

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

  const toggleListening = useCallback(() => {
    if (isListening) {
      recognitionRef.current?.stop()
      setIsListening(false)
    } else {
      try {
        recognitionRef.current?.start()
        setIsListening(true)
      } catch {
        setIsListening(false)
      }
    }
  }, [isListening])

  const audioRef = useRef(null)

  const speakMessage = useCallback(async (text, index) => {
    if (speaking === index) {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current = null
      }
      window.speechSynthesis.cancel()
      setSpeaking(null)
      return
    }

    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
    window.speechSynthesis.cancel()
    setSpeaking(index)

    try {
      const data = await api.post('/api/speech/synthesize', { text: text.slice(0, 3000) })
      if (data.audio) {
        const audioBlob = Uint8Array.from(atob(data.audio), c => c.charCodeAt(0))
        const blob = new Blob([audioBlob], { type: 'audio/mpeg' })
        const url = URL.createObjectURL(blob)
        const audio = new Audio(url)
        audioRef.current = audio
        audio.onended = () => { setSpeaking(null); URL.revokeObjectURL(url) }
        audio.onerror = () => { setSpeaking(null); URL.revokeObjectURL(url) }
        audio.play()
        return
      }
    } catch {
      // Polly unavailable, fall back to browser TTS
    }

    const utterance = new SpeechSynthesisUtterance(text)
    utterance.rate = 1.0
    utterance.onend = () => setSpeaking(null)
    utterance.onerror = () => setSpeaking(null)
    window.speechSynthesis.speak(utterance)
  }, [speaking])

  const doSend = useCallback(async (text) => {
    const msg = (text || input).trim()
    if (!msg || sending) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: msg, timestamp: new Date().toISOString() }])
    setSending(true)
    try {
      const { job_id } = await api.post('/api/chat', { message: msg, session_id: 'default' })
      const result = await pollJob(job_id)
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: result.result?.reply || 'Sorry, I could not generate a response.',
        timestamp: new Date().toISOString(),
      }])
    } catch {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Something went wrong. Please try again.',
        timestamp: new Date().toISOString(),
      }])
    } finally {
      setSending(false)
    }
  }, [input, sending])

  // Auto-speak last assistant message if it was just added
  const prevMsgCount = useRef(0)
  useEffect(() => {
    if (messages.length > prevMsgCount.current) {
      const last = messages[messages.length - 1]
      if (last?.role === 'assistant' && autoSpeak) {
        speakMessage(last.content, messages.length - 1)
      }
    }
    prevMsgCount.current = messages.length
  }, [messages.length])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      doSend()
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
      <div className="flex items-center justify-between px-4 py-3 border-b bg-vida-50 rounded-t-xl">
        <div className="flex items-center gap-2">
          <Sparkles size={18} className="text-vida-600" />
          <span className="font-semibold text-vida-700 text-sm">Ask Vida</span>
          {isListening && (
            <span className="flex items-center gap-1 text-xs text-red-500 font-medium">
              <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
              Listening...
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setAutoSpeak(a => !a)}
            title={autoSpeak ? 'Auto-read ON (Amazon Polly)' : 'Auto-read OFF'}
            className={`p-1 rounded transition-colors ${autoSpeak ? 'text-vida-600 bg-vida-100' : 'text-gray-400 hover:text-gray-600'}`}
          >
            {autoSpeak ? <Volume2 size={15} /> : <VolumeX size={15} />}
          </button>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
            <X size={18} />
          </button>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {loading && (
          <div className="flex justify-center py-8">
            <Loader2 size={24} className="animate-spin text-gray-400" />
          </div>
        )}

        {!loading && messages.length === 0 && (
          <div className="text-center py-6 space-y-4">
            <Sparkles size={36} className="mx-auto text-vida-300" />
            <div>
              <p className="text-sm font-medium text-gray-700">What can Vida help with?</p>
              <p className="text-xs text-gray-400 mt-1">Ask anything about your goals, schedule, or tasks</p>
            </div>
            <div className="grid grid-cols-2 gap-2 px-2">
              {['Plan my day', "What's my top priority?", 'Review my goals', 'What did I accomplish?'].map(q => (
                <button key={q} onClick={() => doSend(q)}
                  className="text-xs text-left px-3 py-2.5 bg-white border border-gray-200 rounded-lg text-gray-600 hover:border-vida-300 hover:bg-vida-50/50 transition-colors">
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] ${msg.role === 'user' ? '' : 'group'}`}>
              <div className={`px-3.5 py-2 rounded-2xl text-sm leading-relaxed ${
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
              {msg.role === 'assistant' && (
                <button onClick={() => speakMessage(msg.content, i)}
                  className="mt-0.5 ml-1 text-gray-300 hover:text-vida-600 transition-colors opacity-0 group-hover:opacity-100">
                  {speaking === i ? <VolumeX size={13} /> : <Volume2 size={13} />}
                </button>
              )}
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

      {messages.length > 0 && messages.length < 4 && !sending && (
        <div className="flex flex-wrap gap-1.5 px-3 pb-1.5">
          {QUICK_ACTIONS.map(action => (
            <button key={action} onClick={() => doSend(action)}
              className="text-[11px] px-2.5 py-1 bg-vida-50 text-vida-700 rounded-full hover:bg-vida-100 transition-colors">
              {action}
            </button>
          ))}
        </div>
      )}

      <div className="border-t px-3 py-2">
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isListening ? 'Listening...' : 'Ask Vida...'}
            rows={1}
            className="flex-1 resize-none px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-vida-500 focus:border-vida-500 outline-none max-h-24"
          />
          {speechSupported && (
            <button
              onClick={toggleListening}
              className={`p-2 rounded-lg transition-colors flex-shrink-0 ${
                isListening ? 'bg-red-500 text-white animate-pulse' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
              title={isListening ? 'Stop listening' : 'Voice input'}
            >
              {isListening ? <MicOff size={16} /> : <Mic size={16} />}
            </button>
          )}
          <button
            onClick={() => doSend()}
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
