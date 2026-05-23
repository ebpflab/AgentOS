import { useState, useRef, useEffect } from 'react'
import { Send, Bot, User } from 'lucide-react'
import { agentsApi } from '../lib/api'
import { useTranslation } from '../i18n'

interface Message { role: 'user' | 'agent'; content: string; timestamp: Date }

export default function ChatPanel({ agentId, agentName }: { agentId: string; agentName: string }) {
  const { t } = useTranslation()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  async function handleSend() {
    if (!input.trim() || loading) return
    const userMsg: Message = { role: 'user', content: input, timestamp: new Date() }
    setMessages(prev => [...prev, userMsg])
    setInput(''); setLoading(true)
    try {
      const res = await agentsApi.run(agentId, input)
      setMessages(prev => [...prev, { role: 'agent', content: res.response, timestamp: new Date() }])
    } catch (e) {
      const errMsg = e instanceof Error ? e.message : t('chat.errorFallback')
      setMessages(prev => [...prev, { role: 'agent', content: t('chat.errorPrefix', errMsg), timestamp: new Date() }])
    } finally { setLoading(false) }
  }

  return (
    <div className="flex flex-col h-[500px] bg-white border border-gray-200 rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex items-center gap-2">
        <Bot className="w-5 h-5 text-blue-600" />
        <span className="font-medium text-sm">{t('chat.with', agentName)}</span>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 text-sm py-12">{t('chat.empty')}</div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
            {msg.role === 'agent' && (
              <div className="bg-blue-100 p-1.5 rounded-full h-7 w-7 flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4 text-blue-600" />
              </div>
            )}
            <div className={`max-w-[75%] rounded-lg px-4 py-2.5 text-sm ${
              msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-800'}`}>
              <p className="whitespace-pre-wrap">{msg.content}</p>
              <p className={`text-xs mt-1 ${msg.role === 'user' ? 'text-blue-200' : 'text-gray-400'}`}>
                {msg.timestamp.toLocaleTimeString()}
              </p>
            </div>
            {msg.role === 'user' && (
              <div className="bg-gray-200 p-1.5 rounded-full h-7 w-7 flex items-center justify-center shrink-0">
                <User className="w-4 h-4 text-gray-600" />
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex gap-3">
            <div className="bg-blue-100 p-1.5 rounded-full h-7 w-7 flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4 text-blue-600" />
            </div>
            <div className="bg-gray-100 rounded-lg px-4 py-3">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:0.15s]" />
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:0.3s]" />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="px-4 py-3 border-t border-gray-200">
        <div className="flex gap-2">
          <input type="text" value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            placeholder={t('chat.placeholder')}
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={loading} />
          <button onClick={handleSend} disabled={loading || !input.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed">
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
