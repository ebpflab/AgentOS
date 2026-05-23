import { useEffect, useState } from 'react'
import { BarChart3, DollarSign, Zap, TrendingUp } from 'lucide-react'
import { metricsApi } from '../lib/api'
import type { AgentMetrics, CostMetrics, TokenMetrics } from '../lib/api'
import { useTranslation } from '../i18n'

export default function Metrics() {
  const { t } = useTranslation()
  const [agentMetrics, setAgentMetrics] = useState<AgentMetrics | null>(null)
  const [costMetrics, setCostMetrics] = useState<CostMetrics | null>(null)
  const [tokenMetrics, setTokenMetrics] = useState<TokenMetrics | null>(null)
  const [period, setPeriod] = useState('7d')

  useEffect(() => { loadMetrics() }, [period])

  async function loadMetrics() {
    const [a, c, tk] = await Promise.allSettled([metricsApi.agents(), metricsApi.cost(period), metricsApi.tokens()])
    if (a.status === 'fulfilled') setAgentMetrics(a.value)
    if (c.status === 'fulfilled') setCostMetrics(c.value)
    if (tk.status === 'fulfilled') setTokenMetrics(tk.value)
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('metrics.title')}</h1>
          <p className="text-sm text-gray-500 mt-1">{t('metrics.subtitle')}</p>
        </div>
        <select value={period} onChange={e => setPeriod(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm">
          <option value="1d">{t('metrics.period.1d')}</option>
          <option value="7d">{t('metrics.period.7d')}</option>
          <option value="30d">{t('metrics.period.30d')}</option>
        </select>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard icon={<BarChart3 className="w-6 h-6 text-blue-600" />} label={t('metrics.totalAgents')} value={agentMetrics?.total_agents ?? 0} />
        <MetricCard icon={<Zap className="w-6 h-6 text-amber-600" />} label={t('metrics.totalTokens')} value={formatNumber(tokenMetrics?.total_tokens ?? 0)} />
        <MetricCard icon={<TrendingUp className="w-6 h-6 text-purple-600" />} label={t('metrics.requests')} value={tokenMetrics?.request_count ?? 0} />
        <MetricCard icon={<DollarSign className="w-6 h-6 text-green-600" />} label={t('metrics.totalCost')} value={`$${(costMetrics?.total_cost_usd ?? 0).toFixed(2)}`} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white border border-gray-200 rounded-lg p-5">
          <h3 className="font-semibold text-gray-900 mb-4">{t('metrics.tokenUsage')}</h3>
          <div className="space-y-4">
            <BarItem label={t('metrics.inputTokens')} value={tokenMetrics?.input_tokens ?? 0} max={tokenMetrics?.total_tokens || 1} color="bg-blue-500" />
            <BarItem label={t('metrics.outputTokens')} value={tokenMetrics?.output_tokens ?? 0} max={tokenMetrics?.total_tokens || 1} color="bg-emerald-500" />
          </div>
          <p className="text-xs text-gray-400 mt-4">
            {t('metrics.tokenSummary', formatNumber(tokenMetrics?.total_tokens ?? 0), tokenMetrics?.request_count ?? 0)}
          </p>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-5">
          <h3 className="font-semibold text-gray-900 mb-4">{t('metrics.agentsByStatus')}</h3>
          {agentMetrics && Object.keys(agentMetrics.by_status).length > 0 ? (
            <div className="space-y-3">
              {Object.entries(agentMetrics.by_status).map(([status, count]) => (
                <div key={status} className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 capitalize">{status}</span>
                  <span className="font-mono text-sm font-medium">{count}</span>
                </div>
              ))}
            </div>
          ) : <p className="text-sm text-gray-400">{t('metrics.noAgentData')}</p>}

          {agentMetrics && Object.keys(agentMetrics.by_provider).length > 0 && (
            <>
              <h4 className="font-medium text-gray-700 mt-6 mb-3">{t('metrics.byProvider')}</h4>
              <div className="space-y-3">
                {Object.entries(agentMetrics.by_provider).map(([provider, count]) => (
                  <div key={provider} className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">{provider}</span>
                    <span className="font-mono text-sm font-medium">{count}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <h3 className="font-semibold text-gray-900 mb-4">{t('metrics.costOverTime')}</h3>
        <div className="h-48 flex items-center justify-center text-gray-400 text-sm">
          <div className="text-center">
            <BarChart3 className="w-10 h-10 mx-auto mb-2 text-gray-300" />
            <p>{t('metrics.chartsHint')}</p>
            <p className="text-xs text-gray-400 mt-1">{t('metrics.chartsSub')}</p>
          </div>
        </div>
      </div>
    </div>
  )
}

function MetricCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string | number }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{label}</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
        </div>
        <div className="bg-gray-50 p-3 rounded-lg">{icon}</div>
      </div>
    </div>
  )
}

function BarItem({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-gray-600">{label}</span>
        <span className="font-mono text-gray-900">{formatNumber(value)}</span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-2">
        <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}
