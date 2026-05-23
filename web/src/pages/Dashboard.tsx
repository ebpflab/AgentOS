import { useEffect, useState } from 'react'
import { Bot, Activity, Zap, DollarSign, AlertTriangle } from 'lucide-react'
import { agentsApi, healthApi, metricsApi } from '../lib/api'
import type { Agent, HealthResponse, AgentMetrics } from '../lib/api'
import { useWebSocket } from '../hooks/useWebSocket'
import AgentCard from '../components/AgentCard'
import { useTranslation } from '../i18n'

export default function Dashboard() {
  const { t } = useTranslation()
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [agents, setAgents] = useState<Agent[]>([])
  const [metrics, setMetrics] = useState<AgentMetrics | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { events } = useWebSocket({ patterns: ['agent.*', 'workflow.*'] })

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 10000)
    return () => clearInterval(interval)
  }, [])

  async function loadData() {
    try {
      const [h, a, m] = await Promise.allSettled([healthApi.check(), agentsApi.list(), metricsApi.agents()])
      if (h.status === 'fulfilled') setHealth(h.value)
      if (a.status === 'fulfilled') setAgents(a.value)
      if (m.status === 'fulfilled') setMetrics(m.value)
      setError(null)
    } catch {
      setError(t('dashboard.error'))
    }
  }

  const statusCounts = agents.reduce<Record<string, number>>((acc, a) => {
    acc[a.status] = (acc[a.status] || 0) + 1
    return acc
  }, {})

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t('dashboard.title')}</h1>
        <p className="text-sm text-gray-500 mt-1">{t('dashboard.subtitle')}</p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2">
          <AlertTriangle className="w-5 h-5" />{error}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={<Bot className="w-6 h-6 text-blue-600" />} label={t('dashboard.totalAgents')}
          value={metrics?.total_agents ?? agents.length}
          sub={health?.providers.length ? t('dashboard.providers', health.providers.length) : ''} />
        <StatCard icon={<Activity className="w-6 h-6 text-green-600" />} label={t('dashboard.running')}
          value={statusCounts['running'] || 0} sub={t('dashboard.stopped', statusCounts['stopped'] || 0)} />
        <StatCard icon={<Zap className="w-6 h-6 text-amber-600" />} label={t('dashboard.recentEvents')}
          value={events.length} sub={t('dashboard.realtime')} />
        <StatCard icon={<DollarSign className="w-6 h-6 text-emerald-600" />} label={t('dashboard.systemStatus')}
          value={health?.status === 'healthy' ? t('common.healthy') : t('common.unknown')}
          sub={health ? t('dashboard.registered', health.agents) : ''}
          valueClass={health?.status === 'healthy' ? 'text-green-600' : 'text-gray-400'} />
      </div>

      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">{t('dashboard.agents')}</h2>
        {agents.length === 0 ? (
          <div className="bg-white border border-gray-200 rounded-lg p-8 text-center text-gray-500">
            {t('dashboard.noAgents')}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {agents.map(agent => <AgentCard key={agent.agent_id} agent={agent} onRefresh={loadData} />)}
          </div>
        )}
      </div>

      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">{t('dashboard.recentEvents')}</h2>
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          {events.length === 0 ? (
            <div className="p-6 text-center text-gray-400">{t('dashboard.waitingEvents')}</div>
          ) : (
            <div className="divide-y divide-gray-100 max-h-72 overflow-y-auto">
              {events.slice(0, 20).map(e => (
                <div key={e.event_id} className="px-4 py-2.5 flex items-center gap-3 text-sm">
                  <span className="font-mono text-xs text-gray-400 w-20 shrink-0">
                    {new Date(e.timestamp * 1000).toLocaleTimeString()}
                  </span>
                  <span className="font-medium text-blue-600 w-40 shrink-0 truncate">{e.topic}</span>
                  <span className="text-gray-600 truncate">
                    {typeof e.data === 'string' ? e.data : JSON.stringify(e.data)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function StatCard({ icon, label, value, sub, valueClass }: {
  icon: React.ReactNode; label: string; value: string | number; sub?: string; valueClass?: string
}) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{label}</p>
          <p className={`text-2xl font-bold mt-1 ${valueClass || 'text-gray-900'}`}>{value}</p>
          {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
        </div>
        <div className="bg-gray-50 p-3 rounded-lg">{icon}</div>
      </div>
    </div>
  )
}
