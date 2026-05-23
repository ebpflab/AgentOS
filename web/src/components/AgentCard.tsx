import { Bot, Play, Square, Trash2 } from 'lucide-react'
import clsx from 'clsx'
import type { Agent } from '../lib/api'
import { agentsApi } from '../lib/api'
import { useTranslation } from '../i18n'

const STATUS_COLORS: Record<string, string> = {
  running: 'bg-green-100 text-green-700',
  stopped: 'bg-gray-100 text-gray-600',
  created: 'bg-blue-100 text-blue-700',
  starting: 'bg-yellow-100 text-yellow-700',
  stopping: 'bg-yellow-100 text-yellow-700',
  error: 'bg-red-100 text-red-700',
}

export default function AgentCard({ agent, onRefresh }: { agent: Agent; onRefresh: () => void }) {
  const { t } = useTranslation()

  async function handleStart() { try { await agentsApi.start(agent.agent_id); onRefresh() } catch {} }
  async function handleStop() { try { await agentsApi.stop(agent.agent_id); onRefresh() } catch {} }
  async function handleDelete() {
    if (!confirm(t('agents.confirmDelete', agent.name))) return
    try { await agentsApi.delete(agent.agent_id); onRefresh() } catch {}
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-sm transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="bg-blue-50 p-2 rounded-lg">
            <Bot className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">{agent.name}</h3>
            <p className="text-xs text-gray-500">{agent.provider}/{agent.model || 'default'}</p>
          </div>
        </div>
        <span className={clsx('px-2 py-0.5 rounded-full text-xs font-medium',
          STATUS_COLORS[agent.status] || 'bg-gray-100 text-gray-600')}>
          {agent.status}
        </span>
      </div>

      {agent.capabilities.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {agent.capabilities.map(cap => (
            <span key={cap} className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded text-xs">{cap}</span>
          ))}
        </div>
      )}

      <div className="mt-3 pt-3 border-t border-gray-100 flex gap-2">
        {agent.status !== 'running' && (
          <button onClick={handleStart}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-green-50 text-green-700 rounded-md text-xs font-medium hover:bg-green-100">
            <Play className="w-3.5 h-3.5" /> {t('agents.start')}
          </button>
        )}
        {agent.status === 'running' && (
          <button onClick={handleStop}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-50 text-amber-700 rounded-md text-xs font-medium hover:bg-amber-100">
            <Square className="w-3.5 h-3.5" /> {t('agents.stop')}
          </button>
        )}
        <button onClick={handleDelete}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-red-50 text-red-700 rounded-md text-xs font-medium hover:bg-red-100 ml-auto">
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  )
}
