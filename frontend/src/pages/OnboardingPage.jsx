import { useState, useRef, useCallback } from 'react'
import { Upload, FileText, Check, ChevronRight, Loader2, Sparkles, X, User, Target, ListTodo, Repeat, AlertCircle, MessageSquare, Calendar, BookOpen, Mic } from 'lucide-react'
import { api, pollJob } from '../lib/api'

const STEPS = ['Input', 'Review', 'Confirm']

const PHASE_OPTIONS = [
  { value: 'student', label: 'Student' },
  { value: 'early_career', label: 'Early Career' },
  { value: 'mid_career', label: 'Mid Career' },
  { value: 'career_change', label: 'Career Change' },
  { value: 'other', label: 'Other' },
]

export default function OnboardingPage({ onComplete }) {
  const [step, setStep] = useState(0)
  const [file, setFile] = useState(null)
  const [processing, setProcessing] = useState(false)
  const [processingText, setProcessingText] = useState('')
  const [error, setError] = useState(null)
  const [extraction, setExtraction] = useState(null)
  const [profile, setProfile] = useState({ name: '', role: '', summary: '', phase: 'other' })
  const [selectedGoals, setSelectedGoals] = useState([])
  const [selectedTasks, setSelectedTasks] = useState([])
  const [selectedHabits, setSelectedHabits] = useState([])
  const [selectedCommitments, setSelectedCommitments] = useState([])
  const [confirmResult, setConfirmResult] = useState(null)
  const [inputMode, setInputMode] = useState(null) // null, 'file', 'text', 'skip'
  const [textInput, setTextInput] = useState('')
  const [skipName, setSkipName] = useState('')
  const [calendarConnected, setCalendarConnected] = useState(false)
  const [connectingCalendar, setConnectingCalendar] = useState(false)
  const fileInputRef = useRef(null)
  const dropRef = useRef(null)

  const connectGoogleCalendar = async () => {
    setConnectingCalendar(true)
    try {
      const data = await api.get('/api/auth/google')
      if (data.url) window.location.href = data.url
    } catch {
      setError('Failed to start Google Calendar connection')
      setConnectingCalendar(false)
    }
  }

  // Check if returning from OAuth callback
  useState(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('connected') === 'google') {
      setCalendarConnected(true)
      window.history.replaceState({}, '', window.location.pathname)
    }
  })

  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    dropRef.current?.classList.add('border-vida-500', 'bg-vida-50')
  }, [])

  const handleDragLeave = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    dropRef.current?.classList.remove('border-vida-500', 'bg-vida-50')
  }, [])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    dropRef.current?.classList.remove('border-vida-500', 'bg-vida-50')
    const droppedFile = e.dataTransfer.files?.[0]
    if (droppedFile) setFile(droppedFile)
  }, [])

  const handleFileSelect = (e) => {
    const selected = e.target.files?.[0]
    if (selected) setFile(selected)
  }

  const contentTypeFor = (name) => {
    if (name.endsWith('.pdf')) return 'application/pdf'
    if (name.endsWith('.md')) return 'text/markdown'
    return 'text/plain'
  }

  const processExtraction = async (ext) => {
    if (!ext) throw new Error('AI extraction returned empty')
    setExtraction(ext)
    setProfile({
      name: ext.profile?.name || '',
      role: ext.profile?.role || '',
      summary: ext.profile?.summary || '',
      phase: ext.profile?.phase || 'other',
    })
    setSelectedGoals([])
    setSelectedTasks([])
    setSelectedHabits([])
    setSelectedCommitments([])
    setStep(1)
  }

  const handleUpload = async () => {
    if (!file) return
    setProcessing(true)
    setError(null)
    try {
      setProcessingText('Getting upload URL...')
      const presign = await api.post('/api/onboard/presign', {
        file_name: file.name,
        content_type: contentTypeFor(file.name),
      })
      setProcessingText('Uploading your document...')
      await fetch(presign.upload_url, {
        method: 'PUT',
        body: file,
        headers: { 'Content-Type': contentTypeFor(file.name) },
      })
      setProcessingText('AI is reading your document and extracting your profile...')
      const job = await api.post('/api/onboard/process', {
        s3_key: presign.s3_key,
        doc_id: presign.doc_id,
      })
      setProcessingText('Analyzing — extracting profile, goals, and commitments...')
      const result = await pollJob(job.job_id)
      await processExtraction(result.result?.extraction)
    } catch (err) {
      setError(err.message || 'Upload failed')
    } finally {
      setProcessing(false)
      setProcessingText('')
    }
  }

  const handleTextSubmit = async () => {
    if (!textInput.trim()) return
    setProcessing(true)
    setError(null)
    try {
      setProcessingText('AI is analyzing your input...')
      const job = await api.post('/api/onboard/process', { text: textInput.trim() })
      setProcessingText('Extracting profile, goals, and commitments...')
      const result = await pollJob(job.job_id)
      await processExtraction(result.result?.extraction)
    } catch (err) {
      setError(err.message || 'Processing failed')
    } finally {
      setProcessing(false)
      setProcessingText('')
    }
  }

  const toggleItem = (list, setList, idx) => {
    setList(prev => prev.includes(idx) ? prev.filter(i => i !== idx) : [...prev, idx])
  }

  const handleConfirm = async () => {
    setProcessing(true)
    setError(null)
    try {
      const goals = (extraction?.suggestions?.goals || []).filter((_, i) => selectedGoals.includes(i))
      const tasks = (extraction?.suggestions?.tasks || []).filter((_, i) => selectedTasks.includes(i))
      const habits = (extraction?.suggestions?.habits || []).filter((_, i) => selectedHabits.includes(i))
      const commitments = (extraction?.commitments || []).filter((_, i) => selectedCommitments.includes(i))
      const result = await api.post('/api/onboard/confirm', {
        profile: { ...profile, onboarded: true },
        facts: extraction?.facts || [],
        suggestions: { goals, tasks, habits },
        commitments,
      })
      setConfirmResult(result)
      setStep(2)
    } catch (err) {
      setError(err.message || 'Confirmation failed')
    } finally {
      setProcessing(false)
    }
  }

  const handleSkip = async () => {
    if (!skipName.trim()) return
    setProcessing(true)
    try {
      await api.post('/api/onboard/confirm', {
        profile: { name: skipName.trim(), onboarded: true },
        facts: [],
        suggestions: { goals: [], tasks: [], habits: [] },
        commitments: [],
      })
      onComplete({ name: skipName.trim(), onboarded: true })
    } catch (err) {
      setError(err.message || 'Setup failed')
    } finally {
      setProcessing(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-vida-50 via-white to-purple-50">
      <div className="bg-gradient-to-r from-vida-600 to-vida-700 text-white py-12 px-6">
        <div className="max-w-3xl mx-auto text-center">
          <h1 className="text-4xl font-bold mb-3">Welcome to Vida</h1>
          <p className="text-vida-100 text-lg">Your AI life assistant. Drop a file and watch the magic happen.</p>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-6 py-6">
        <div className="flex items-center justify-center gap-2">
          {STEPS.map((label, i) => (
            <div key={label} className="flex items-center gap-2">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold transition-colors ${
                i < step ? 'bg-vida-600 text-white' : i === step ? 'bg-vida-600 text-white ring-4 ring-vida-200' : 'bg-gray-200 text-gray-500'
              }`}>
                {i < step ? <Check size={16} /> : i + 1}
              </div>
              <span className={`text-sm font-medium ${i <= step ? 'text-vida-700' : 'text-gray-400'}`}>{label}</span>
              {i < STEPS.length - 1 && <ChevronRight size={16} className="text-gray-300 mx-2" />}
            </div>
          ))}
        </div>
      </div>

      {error && (
        <div className="max-w-3xl mx-auto px-6 mb-4">
          <div className="bg-red-50 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2 text-sm">
            <AlertCircle size={16} />{error}
            <button onClick={() => setError(null)} className="ml-auto"><X size={14} /></button>
          </div>
        </div>
      )}

      <div className="max-w-3xl mx-auto px-6 pb-12">
        {step === 0 && (
          <div className="space-y-6">
            {processing ? (
              <div className="bg-white rounded-2xl shadow-lg p-12 text-center">
                <Loader2 size={48} className="animate-spin text-vida-600 mx-auto mb-4" />
                <p className="text-lg font-medium text-gray-700">{processingText}</p>
                <p className="text-sm text-gray-400 mt-2">This usually takes 10-30 seconds</p>
              </div>
            ) : inputMode === 'skip' ? (
              <div className="bg-white rounded-2xl shadow-lg p-8 space-y-6">
                <div className="text-center">
                  <User size={40} className="text-vida-600 mx-auto mb-3" />
                  <h2 className="text-xl font-semibold text-gray-800">Quick Setup</h2>
                  <p className="text-sm text-gray-500 mt-1">You can always upload a document later from the Library.</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">What should Vida call you?</label>
                  <input type="text" value={skipName} onChange={e => setSkipName(e.target.value)} placeholder="Your name"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-vida-500 focus:border-vida-500 outline-none" autoFocus />
                </div>
                <div className="flex items-center justify-between">
                  <button onClick={() => setInputMode(null)} className="text-sm text-gray-500 hover:text-gray-700 underline">Back</button>
                  <button onClick={handleSkip} disabled={!skipName.trim() || processing}
                    className="px-6 py-3 bg-vida-600 text-white rounded-lg font-medium hover:bg-vida-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
                    {processing ? <Loader2 size={18} className="animate-spin" /> : 'Get Started'}
                  </button>
                </div>
              </div>
            ) : inputMode === 'file' ? (
              <div className="space-y-4">
                <div ref={dropRef} onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className="bg-white rounded-2xl shadow-lg border-2 border-dashed border-gray-300 p-12 text-center cursor-pointer hover:border-vida-400 hover:bg-vida-50/30 transition-all">
                  <input ref={fileInputRef} type="file" accept=".txt,.md,.pdf" onChange={handleFileSelect} className="hidden" />
                  {file ? (
                    <div className="space-y-3">
                      <FileText size={48} className="text-vida-600 mx-auto" />
                      <p className="text-lg font-medium text-gray-800">{file.name}</p>
                      <p className="text-sm text-gray-500">{(file.size / 1024).toFixed(1)} KB</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <Upload size={48} className="text-gray-400 mx-auto" />
                      <p className="text-lg font-medium text-gray-600">Drop your resume, goals doc, or brain-dump here</p>
                      <p className="text-sm text-gray-400">Accepts .txt, .md, .pdf</p>
                    </div>
                  )}
                </div>
                <div className="flex items-center justify-between">
                  <button onClick={() => { setInputMode(null); setFile(null) }} className="text-sm text-gray-500 hover:text-gray-700 underline">Back</button>
                  <button onClick={handleUpload} disabled={!file}
                    className="px-6 py-3 bg-vida-600 text-white rounded-lg font-medium hover:bg-vida-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-2">
                    <Sparkles size={18} />Analyze with AI
                  </button>
                </div>
              </div>
            ) : inputMode === 'text' ? (
              <div className="space-y-4">
                <div className="bg-white rounded-2xl shadow-lg p-6 space-y-4">
                  <h3 className="text-lg font-semibold text-gray-800">Tell Vida about yourself</h3>
                  <p className="text-sm text-gray-500">Paste your resume, describe your goals, or dump everything on your mind. Vida will organize it for you.</p>
                  <textarea value={textInput} onChange={e => setTextInput(e.target.value)} rows={10} placeholder={"Example:\nI'm a software engineer with 3 years of experience...\nMy goals this year: learn system design, get promoted, run a half marathon...\nUpcoming deadlines: project demo on Nov 15, performance review in December..."}
                    className="w-full px-4 py-3 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-vida-500 focus:border-vida-500 outline-none resize-none" autoFocus />
                </div>
                <div className="flex items-center justify-between">
                  <button onClick={() => { setInputMode(null); setTextInput('') }} className="text-sm text-gray-500 hover:text-gray-700 underline">Back</button>
                  <button onClick={handleTextSubmit} disabled={!textInput.trim()}
                    className="px-6 py-3 bg-vida-600 text-white rounded-lg font-medium hover:bg-vida-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-2">
                    <Sparkles size={18} />Analyze with AI
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                <div className="bg-white rounded-2xl shadow-lg p-6">
                  <h3 className="text-lg font-semibold text-gray-800 mb-1">How would you like to get started?</h3>
                  <p className="text-sm text-gray-500 mb-5">Choose how to share your goals, background, and commitments with Vida.</p>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <button onClick={() => setInputMode('file')}
                      className="flex flex-col items-center gap-3 p-5 rounded-xl border-2 border-gray-200 hover:border-vida-500 hover:bg-vida-50/30 transition-all text-center">
                      <Upload size={32} className="text-vida-600" />
                      <div>
                        <div className="text-sm font-semibold text-gray-800">Upload a File</div>
                        <div className="text-xs text-gray-500 mt-1">Resume, goals doc, or brain-dump (.pdf, .txt, .md)</div>
                      </div>
                    </button>
                    <button onClick={() => setInputMode('text')}
                      className="flex flex-col items-center gap-3 p-5 rounded-xl border-2 border-gray-200 hover:border-vida-500 hover:bg-vida-50/30 transition-all text-center">
                      <MessageSquare size={32} className="text-vida-600" />
                      <div>
                        <div className="text-sm font-semibold text-gray-800">Type or Paste</div>
                        <div className="text-xs text-gray-500 mt-1">Write about your goals, paste your bio, or brain-dump</div>
                      </div>
                    </button>
                    <button disabled
                      className="flex flex-col items-center gap-3 p-5 rounded-xl border-2 border-gray-200 text-center opacity-50 cursor-not-allowed relative">
                      <Mic size={32} className="text-gray-400" />
                      <div>
                        <div className="text-sm font-semibold text-gray-600">Voice Input</div>
                        <div className="text-xs text-gray-400 mt-1">Talk about your goals and Vida listens</div>
                      </div>
                      <span className="absolute top-2 right-2 text-[10px] bg-gray-200 text-gray-500 px-2 py-0.5 rounded-full font-medium">Soon</span>
                    </button>
                  </div>
                </div>

                <div className="bg-white rounded-2xl shadow-lg p-6">
                  <h3 className="text-lg font-semibold text-gray-800 mb-1">Connect Your Tools</h3>
                  <p className="text-sm text-gray-500 mb-4">Let Vida pull in your existing schedule and notes for smarter planning.</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {calendarConnected ? (
                      <div className="flex items-center gap-4 p-4 rounded-xl border-2 border-green-300 bg-green-50 text-left">
                        <Check size={28} className="text-green-600 flex-shrink-0" />
                        <div>
                          <div className="text-sm font-semibold text-green-700">Google Calendar Connected</div>
                          <div className="text-xs text-green-600">Your events will sync when you finish onboarding</div>
                        </div>
                      </div>
                    ) : (
                      <button onClick={connectGoogleCalendar} disabled={connectingCalendar}
                        className="flex items-center gap-4 p-4 rounded-xl border-2 border-blue-200 hover:border-blue-400 hover:bg-blue-50/30 transition-all text-left">
                        {connectingCalendar ? <Loader2 size={28} className="text-blue-500 flex-shrink-0 animate-spin" /> : <Calendar size={28} className="text-blue-500 flex-shrink-0" />}
                        <div>
                          <div className="text-sm font-semibold text-gray-800">Google Calendar</div>
                          <div className="text-xs text-gray-500">Import events, deadlines, and meetings</div>
                        </div>
                      </button>
                    )}
                    <button disabled className="flex items-center gap-4 p-4 rounded-xl border-2 border-gray-200 text-left opacity-50 cursor-not-allowed relative">
                      <BookOpen size={28} className="text-gray-700 flex-shrink-0" />
                      <div>
                        <div className="text-sm font-semibold text-gray-700">Notion</div>
                        <div className="text-xs text-gray-400">Sync projects, tasks, and knowledge base</div>
                      </div>
                      <span className="absolute top-2 right-2 text-[10px] bg-gray-200 text-gray-500 px-2 py-0.5 rounded-full font-medium">Soon</span>
                    </button>
                  </div>
                </div>

                <div className="bg-vida-50/50 rounded-xl p-4">
                  <h4 className="text-sm font-semibold text-vida-700 mb-2">Suggestions for what to share</h4>
                  <ul className="text-xs text-vida-600 space-y-1.5">
                    <li>Your resume or LinkedIn bio — Vida extracts skills, experience, and career goals</li>
                    <li>A goals document — yearly goals, quarterly OKRs, or a bucket list</li>
                    <li>A brain-dump — everything on your mind, Vida will organize it into goals and tasks</li>
                    <li>Deadlines and commitments — upcoming exams, project due dates, events</li>
                  </ul>
                </div>

                <div className="text-center">
                  <button onClick={() => setInputMode('skip')} className="text-sm text-gray-500 hover:text-gray-700 underline">
                    Skip for now — set up manually
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {step === 1 && extraction && (
          <div className="space-y-6">
            <div className="bg-white rounded-2xl shadow-lg p-6 space-y-4">
              <div className="flex items-center gap-2 text-vida-700 font-semibold text-lg"><User size={20} /> Your Profile</div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Name</label>
                  <input value={profile.name} onChange={e => setProfile(p => ({ ...p, name: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-vida-500 focus:border-vida-500 outline-none" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Role</label>
                  <input value={profile.role} onChange={e => setProfile(p => ({ ...p, role: e.target.value }))}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-vida-500 focus:border-vida-500 outline-none" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Summary</label>
                <textarea value={profile.summary} onChange={e => setProfile(p => ({ ...p, summary: e.target.value }))} rows={3}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-vida-500 focus:border-vida-500 outline-none resize-none" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Life Phase</label>
                <select value={profile.phase} onChange={e => setProfile(p => ({ ...p, phase: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-vida-500 focus:border-vida-500 outline-none bg-white">
                  {PHASE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
            </div>

            {extraction.facts?.length > 0 && (
              <div className="bg-white rounded-2xl shadow-lg p-6 space-y-3">
                <h3 className="text-vida-700 font-semibold flex items-center gap-2"><FileText size={18} /> Extracted Facts</h3>
                <div className="flex flex-wrap gap-2">
                  {extraction.facts.map((f, i) => (
                    <span key={i} className="inline-flex items-center gap-1 px-3 py-1.5 bg-gray-100 text-gray-700 rounded-full text-xs font-medium">
                      <span className="text-vida-600 font-semibold">{f.category}:</span> {f.text}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {extraction.suggestions?.goals?.length > 0 && (
              <div className="bg-white rounded-2xl shadow-lg p-6 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-vida-700 font-semibold flex items-center gap-2"><Target size={18} /> Suggested Goals</h3>
                  <button onClick={() => setSelectedGoals(prev => prev.length === extraction.suggestions.goals.length ? [] : extraction.suggestions.goals.map((_, i) => i))}
                    className="text-xs text-vida-600 hover:text-vida-800 font-medium">
                    {selectedGoals.length === extraction.suggestions.goals.length ? 'Deselect All' : 'Select All'}
                  </button>
                </div>
                <div className="space-y-2">
                  {extraction.suggestions.goals.map((g, i) => (
                    <label key={i} className="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50 cursor-pointer">
                      <input type="checkbox" checked={selectedGoals.includes(i)}
                        onChange={() => toggleItem(selectedGoals, setSelectedGoals, i)}
                        className="mt-0.5 w-4 h-4 text-vida-600 rounded border-gray-300 focus:ring-vida-500" />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-800">{g.title}</div>
                        {g.description && <div className="text-xs text-gray-500 mt-0.5">{g.description}</div>}
                        <div className="flex gap-2 mt-1">
                          <span className="text-xs px-2 py-0.5 bg-vida-50 text-vida-700 rounded">{g.category}</span>
                          <span className="text-xs px-2 py-0.5 bg-orange-50 text-orange-700 rounded">{g.priority}</span>
                          {g.target_date && <span className="text-xs px-2 py-0.5 bg-blue-50 text-blue-700 rounded">{g.target_date}</span>}
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            )}

            {extraction.suggestions?.tasks?.length > 0 && (
              <div className="bg-white rounded-2xl shadow-lg p-6 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-vida-700 font-semibold flex items-center gap-2"><ListTodo size={18} /> Suggested Tasks</h3>
                  <button onClick={() => setSelectedTasks(prev => prev.length === extraction.suggestions.tasks.length ? [] : extraction.suggestions.tasks.map((_, i) => i))}
                    className="text-xs text-vida-600 hover:text-vida-800 font-medium">
                    {selectedTasks.length === extraction.suggestions.tasks.length ? 'Deselect All' : 'Select All'}
                  </button>
                </div>
                <div className="space-y-2">
                  {extraction.suggestions.tasks.map((t, i) => (
                    <label key={i} className="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50 cursor-pointer">
                      <input type="checkbox" checked={selectedTasks.includes(i)}
                        onChange={() => toggleItem(selectedTasks, setSelectedTasks, i)}
                        className="mt-0.5 w-4 h-4 text-vida-600 rounded border-gray-300 focus:ring-vida-500" />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-800">{t.title}</div>
                        <div className="flex gap-2 mt-1">
                          <span className="text-xs px-2 py-0.5 bg-orange-50 text-orange-700 rounded">{t.priority}</span>
                          {t.estimated_minutes && <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-600 rounded">{t.estimated_minutes}min</span>}
                          {t.due_date && <span className="text-xs px-2 py-0.5 bg-blue-50 text-blue-700 rounded">Due: {t.due_date}</span>}
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            )}

            {extraction.suggestions?.habits?.length > 0 && (
              <div className="bg-white rounded-2xl shadow-lg p-6 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-vida-700 font-semibold flex items-center gap-2"><Repeat size={18} /> Suggested Habits</h3>
                  <button onClick={() => setSelectedHabits(prev => prev.length === extraction.suggestions.habits.length ? [] : extraction.suggestions.habits.map((_, i) => i))}
                    className="text-xs text-vida-600 hover:text-vida-800 font-medium">
                    {selectedHabits.length === extraction.suggestions.habits.length ? 'Deselect All' : 'Select All'}
                  </button>
                </div>
                <div className="space-y-2">
                  {extraction.suggestions.habits.map((h, i) => (
                    <label key={i} className="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50 cursor-pointer">
                      <input type="checkbox" checked={selectedHabits.includes(i)}
                        onChange={() => toggleItem(selectedHabits, setSelectedHabits, i)}
                        className="mt-0.5 w-4 h-4 text-vida-600 rounded border-gray-300 focus:ring-vida-500" />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-800">{h.name}</div>
                        <div className="text-xs text-gray-500 mt-0.5">{h.reason}</div>
                        <span className="text-xs px-2 py-0.5 bg-green-50 text-green-700 rounded mt-1 inline-block">{h.frequency}</span>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            )}

            {extraction.commitments?.length > 0 && (
              <div className="bg-white rounded-2xl shadow-lg p-6 space-y-3">
                <h3 className="text-vida-700 font-semibold flex items-center gap-2"><AlertCircle size={18} /> Commitments Found</h3>
                <div className="space-y-2">
                  {extraction.commitments.map((c, i) => (
                    <label key={i} className="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50 cursor-pointer border border-amber-200 bg-amber-50/50">
                      <input type="checkbox" checked={selectedCommitments.includes(i)}
                        onChange={() => toggleItem(selectedCommitments, setSelectedCommitments, i)}
                        className="mt-0.5 w-4 h-4 text-vida-600 rounded border-gray-300 focus:ring-vida-500" />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-800">{c.title}</div>
                        {c.source_text && <div className="text-xs text-gray-500 mt-1 italic">"{c.source_text}"</div>}
                        <div className="flex gap-2 mt-1">
                          <span className="text-xs px-2 py-0.5 bg-amber-100 text-amber-800 rounded">{c.type}</span>
                          {c.due_date && <span className="text-xs px-2 py-0.5 bg-blue-50 text-blue-700 rounded">Due: {c.due_date}</span>}
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            )}

            <div className="flex justify-end gap-3">
              <button onClick={() => { setStep(0); setExtraction(null); setFile(null) }}
                className="px-5 py-2.5 text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm font-medium">Start Over</button>
              <button onClick={handleConfirm} disabled={processing}
                className="px-6 py-2.5 bg-vida-600 text-white rounded-lg font-medium hover:bg-vida-700 disabled:opacity-40 transition-colors flex items-center gap-2">
                {processing ? <Loader2 size={16} className="animate-spin" /> : <Check size={16} />}Confirm & Create
              </button>
            </div>
          </div>
        )}

        {step === 2 && confirmResult && (
          <div className="bg-white rounded-2xl shadow-lg p-10 text-center space-y-6">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto">
              <Check size={32} className="text-green-600" />
            </div>
            <h2 className="text-2xl font-bold text-gray-800">You're all set, {profile.name}!</h2>
            <p className="text-gray-500">Vida has set up your dashboard with everything from your document.</p>
            <div className="flex justify-center gap-6 text-sm">
              <div className="text-center">
                <div className="text-2xl font-bold text-vida-600">{confirmResult.created?.goals || 0}</div>
                <div className="text-gray-500">Goals</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-vida-600">{confirmResult.created?.tasks || 0}</div>
                <div className="text-gray-500">Tasks</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-vida-600">{confirmResult.created?.habits || 0}</div>
                <div className="text-gray-500">Habits</div>
              </div>
            </div>
            <button onClick={() => onComplete({ ...profile, onboarded: true })}
              className="px-8 py-3 bg-vida-600 text-white rounded-lg font-medium hover:bg-vida-700 transition-colors text-lg">
              Open My Dashboard
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
