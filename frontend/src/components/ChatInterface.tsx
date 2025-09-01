'use client'

import { useState, useRef, useEffect } from 'react'
import { Send, MessageCircle, FileText, Eye, EyeOff } from 'lucide-react'

interface Message {
  id: string
  type: 'user' | 'assistant'
  content: string
  citations?: Citation[]
}

interface Citation {
  chunk_id: number
  content: string
  document: {
    id: string
    name: string
  }
  citation_locator?: any
}

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [showRetrieval, setShowRetrieval] = useState(false)
  const [useRetrieval, setUseRetrieval] = useState(true)
  const [limitToBatch, setLimitToBatch] = useState(true)
  const [batchDocIds, setBatchDocIds] = useState<string[]>([])
  const [batchId, setBatchId] = useState<string | null>(null)
  const [pinnedBatch, setPinnedBatch] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Load current batch and optional query param batch_id
  useEffect(() => {
    try {
      // If query has batch_id, prefer it and pin
      const url = new URL(window.location.href)
      const qBatch = url.searchParams.get('batch_id')
      if (qBatch) {
        setBatchId(qBatch)
        setPinnedBatch(true)
        localStorage.setItem('current_batch_id', qBatch)
        // Fetch its docs for display
        fetch(`/api/uploads/batches/${qBatch}`)
          .then(r => r.ok ? r.json() : null)
          .then(data => {
            if (data && Array.isArray(data.documents)) {
              const ids = data.documents.map((d: any) => d.id)
              setBatchDocIds(ids)
              localStorage.setItem('current_batch_document_ids', JSON.stringify(ids))
            }
          })
          .catch(() => {})
      }

      const keyNew = 'current_batch_document_ids'
      const rawNew = typeof window !== 'undefined' ? localStorage.getItem(keyNew) : null
      let ids: string[] = rawNew ? JSON.parse(rawNew) : []
      // Fallback to old key
      if (!ids?.length) {
        const keyOld = 'recent_document_ids'
        const rawOld = typeof window !== 'undefined' ? localStorage.getItem(keyOld) : null
        ids = rawOld ? JSON.parse(rawOld) : []
      }
      setBatchDocIds(ids)
      const rawBatchId = typeof window !== 'undefined' ? localStorage.getItem('current_batch_id') : null
      if (rawBatchId) setBatchId(rawBatchId)
      const onStorage = (e: StorageEvent) => {
        if (pinnedBatch) return
        if (e.key === keyNew) {
          const next: string[] = e.newValue ? JSON.parse(e.newValue) : []
          setBatchDocIds(next)
        }
        if (e.key === 'current_batch_id') {
          setBatchId(e.newValue)
        }
      }
      window.addEventListener('storage', onStorage)
      return () => window.removeEventListener('storage', onStorage)
    } catch (e) {
      // ignore
    }
  }, [pinnedBatch])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: input
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    try {
      // Add placeholder assistant message
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: ''
      }
      setMessages(prev => [...prev, assistantMessage])

      // Stream the response
      // Refresh batch IDs right before sending (storage event doesn't fire in same tab)
      try {
        const raw = typeof window !== 'undefined' ? localStorage.getItem('current_batch_document_ids') : null
        if (raw) {
          const ids: string[] = JSON.parse(raw)
          if (Array.isArray(ids)) setBatchDocIds(ids)
        }
        const rawId = typeof window !== 'undefined' ? localStorage.getItem('current_batch_id') : null
        if (rawId && !pinnedBatch) setBatchId(rawId)
      } catch {}

      const useTopK = useRetrieval && (!limitToBatch || batchDocIds.length > 0) ? 5 : 0
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: input,
          top_k: useTopK,
          stream: true,
          // Prefer server-enforced batch scoping
          batch_id: limitToBatch ? batchId : undefined,
          // Keep document_ids for fallback visibility, but server will prefer batch_id
          document_ids: limitToBatch ? batchDocIds : undefined,
        })
      })

      if (!response.ok) {
        throw new Error('Failed to get response')
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error('No response body')

      let citations: Citation[] = []
      let answer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = new TextDecoder().decode(value)
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              
              if (data.type === 'citations') {
                citations = data.citations
              } else if (data.type === 'token') {
                answer += data.content
                // Update the assistant message with streaming content
                setMessages(prev => prev.map(msg => 
                  msg.id === assistantMessage.id 
                    ? { ...msg, content: answer, citations }
                    : msg
                ))
              }
            } catch (e) {
              // Ignore parsing errors for incomplete JSON
            }
          }
        }
      }

    } catch (error) {
      console.error('Chat error:', error)
      setMessages(prev => prev.map(msg => 
        msg.id === (Date.now() + 1).toString()
          ? { ...msg, content: 'Sorry, I encountered an error. Please try again.' }
          : msg
      ))
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">
          Chat & Ask Questions
        </h2>
        <p className="text-gray-600">
          Ask questions about your uploaded documents and get AI-powered answers
        </p>
      </div>

      {/* Chat Messages */}
      <div className="bg-white rounded-lg border shadow-sm mb-6">
        <div className="p-4 border-b bg-gray-50">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-medium text-gray-900">Chat</h3>
            <button
              onClick={() => setShowRetrieval(!showRetrieval)}
              className="flex items-center space-x-2 text-sm text-gray-600 hover:text-gray-900"
            >
              {showRetrieval ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              <span>{showRetrieval ? 'Hide' : 'Show'} retrieval</span>
            </button>
          </div>
          <div className="mt-2 flex items-center space-x-2 text-sm text-gray-700">
            <label className="flex items-center space-x-2">
              <input type="checkbox" checked={useRetrieval} onChange={(e) => setUseRetrieval(e.target.checked)} />
              <span>Use retrieval (RAG)</span>
            </label>
            <label className="flex items-center space-x-2">
              <input type="checkbox" checked={limitToBatch} onChange={(e) => setLimitToBatch(e.target.checked)} />
              <span>Limit to current upload batch</span>
            </label>
            {limitToBatch && (
              <span className="text-xs text-gray-500">Batch {batchId ? batchId.slice(0,6) : '—'} • {batchDocIds.length} doc(s)</span>
            )}
            <label className="flex items-center space-x-2">
              <input type="checkbox" checked={pinnedBatch} onChange={(e) => setPinnedBatch(e.target.checked)} />
              <span>Pin batch</span>
            </label>
            <button
              onClick={async () => {
                try {
                  const resp = await fetch('/api/uploads/batches', { method: 'POST', headers: { 'Content-Type': 'application/json' } })
                  if (resp.ok) {
                    const data = await resp.json()
                    const id = data.id as string
                    setBatchId(id)
                    setBatchDocIds([])
                    setPinnedBatch(false)
                    localStorage.setItem('current_batch_id', id)
                    localStorage.setItem('current_batch_document_ids', JSON.stringify([]))
                  }
                } catch {}
              }}
              className="text-blue-600 hover:text-blue-800"
            >
              New Batch
            </button>
            <button
              onClick={async () => {
                try {
                  const url = new URL(window.location.href)
                  if (batchId) {
                    url.searchParams.set('batch_id', batchId)
                  }
                  await navigator.clipboard.writeText(url.toString())
                } catch {}
              }}
              className="text-gray-600 hover:text-gray-900"
            >
              Copy Batch Link
            </button>
          </div>
        </div>

        <div className="h-96 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 ? (
            <div className="text-center text-gray-500 py-8">
              <MessageCircle className="mx-auto h-12 w-12 mb-4" />
              <p>Start a conversation by asking a question about your documents</p>
            </div>
          ) : (
            messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                    message.type === 'user'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-900'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{message.content}</p>
                  
                  {/* Citations */}
                  {message.type === 'assistant' && message.citations && showRetrieval && (
                    <div className="mt-4 pt-3 border-t border-gray-200">
                      <div className="flex items-center space-x-2 mb-3">
                        <FileText className="h-4 w-4 text-gray-500" />
                        <p className="text-sm font-medium text-gray-700">Sources</p>
                      </div>
                      <div className="space-y-3">
                        {message.citations.map((citation, index) => (
                          <div key={index} className="bg-blue-50 border border-blue-200 rounded-lg p-3 hover:bg-blue-100 transition-colors">
                            <div className="flex items-start space-x-3">
                              <div className="flex-shrink-0">
                                <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
                                  <FileText className="h-4 w-4 text-white" />
                                </div>
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-semibold text-gray-900 truncate">
                                  {citation.document.name}
                                </p>
                                <p className="text-sm text-gray-700 mt-1 line-clamp-3">
                                  {citation.content}
                                </p>
                                {citation.citation_locator && (
                                  <p className="text-xs text-blue-600 mt-1">
                                    Page {citation.citation_locator.page || 'N/A'}
                                  </p>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
          
          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-gray-100 text-gray-900 max-w-xs lg:max-w-md px-4 py-2 rounded-lg">
                <div className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Form */}
      <form onSubmit={handleSubmit} className="flex space-x-4">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about your documents..."
          className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-black"
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={!input.trim() || isLoading}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
        >
          <Send className="h-4 w-4" />
          <span>Send</span>
        </button>
      </form>
    </div>
  )
}
