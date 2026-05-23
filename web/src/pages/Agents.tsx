import { useEffect, useState } from 'react'
import { Bot, Plus, X } from 'lucide-react'
import { agentsApi } from '../lib/api'
import type { Agent, AgentCreateRequest } from '../lib/api'
import AgentCard from '../components/AgentCard'
import ChatPanel from '../components/ChatPanel'
import { useTranslation } from '../i18n'

export default function Agents() {
  const { t } = useTranslation()
  const [agents, setAgents] = useState<Agent[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [chatAgent, setChatAgent] = useState<Agent | null>(null)
  const [loading, setLoading] = useState(true)

  async function loadAgents() {
    try { const data = await agentsApi.list(); setAgents(data) } catch { /* API not running */ }
    setLoading(false)
  }
  useEffect(() => { loadAgents() }, [])

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('agents.title')}</h1>
          <p className="text-sm text-gray-500 mt-1">{t('agents.subtitle', agents.length)}</p>
        </div>
        <button onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700">
          <Plus className="w-4 h-4" /> {t('agents.createBtn')}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          {loading ? (
            <div className="bg-white border border-gray-200 rounded-lg p-8 text-center text-gray-400">
              {t('agents.loading')}
            </div>
          ) : agents.length === 0 ? (
            <div className="bg-white border border-gray-200 rounded-lg p-8 text-center text-gray-500">
              <Bot className="w-12 h-12 mx-auto mb-3 text-gray-300" />
              <p className="font-medium">{t('agents.empty')}</p>
              <p className="text-sm mt-1">{t('agents.emptyHint')}</p>
            </div>
          ) : (
            agents.map(agent => (
              <div key={agent.agent_id} onClick={() => setChatAgent(agent)} className="cursor-pointer">
                <AgentCard agent={agent} onRefresh={loadAgents} />
              </div>
            ))
          )}
        </div>

        <div>
          {chatAgent ? (
            <ChatPanel agentId={chatAgent.agent_id} agentName={chatAgent.name} />
          ) : (
            <div className="bg-white border border-gray-200 rounded-lg p-8 text-center text-gray-400 h-[500px] flex items-center justify-center">
              <div>
                <Bot className="w-10 h-10 mx-auto mb-3 text-gray-300" />
                <p className="text-sm">{t('agents.selectToChat')}</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {showCreate && <CreateAgentDialog onClose={() => setShowCreate(false)} onCreated={loadAgents} />}
    </div>
  )
}

function CreateAgentDialog({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const { t } = useTranslation()
  const [form, setForm] = useState<AgentCreateRequest>({
    name: '', instructions: 'You are a helpful assistant.', provider: 'openai', model: 'gpt-4.1', capabilities: [],
  })
  const [capsInput, setCapsInput] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault(); setSaving(true); setError('')
    try {
      await agentsApi.create({ ...form, capabilities: capsInput.split(',').map(s => s.trim()).filter(Boolean) })
      onCreated(); onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : t('agents.createFailed'))
    } finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{t('agents.dialogTitle')}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="w-5 h-5" /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('agents.fieldName')}</label>
            <input required value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="MyAgent" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('agents.fieldInstructions')}</label>
            <textarea rows={3} value={form.instructions} onChange={e => setForm(f => ({ ...f, instructions: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('agents.fieldProvider')}</label>
              <select value={form.provider} onChange={e => setForm(f => ({ ...f, provider: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="ollama">Ollama</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('agents.fieldModel')}</label>
              <input value={form.model} onChange={e => setForm(f => ({ ...f, model: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" placeholder="gpt-4.1" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('agents.fieldCapabilities')}</label>
            <input value={capsInput} onChange={e => setCapsInput(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
              placeholder="coding, review, python" />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-lg">
              {t('common.cancel')}
            </button>
            <button type="submit" disabled={saving}
              className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50">
              {saving ? t('agents.creating') : t('agents.dialogTitle')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
