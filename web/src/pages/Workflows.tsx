import { useEffect, useState } from 'react'
import { GitBranch, AlertTriangle, CheckCircle, Loader2, Bot, Clock } from 'lucide-react'
import clsx from 'clsx'
import { useTranslation } from '../i18n'
import { workflowsApi, agentsApi } from '../lib/api'
import type { Agent } from '../lib/api'

type TemplateType = 'pipeline' | 'research' | 'approval' | 'escalation'

interface WorkflowTemplate {
  type: TemplateType
  nameKey: string
  descKey: string
  agents_required: number
}

const TEMPLATES: WorkflowTemplate[] = [
  { type: 'pipeline', nameKey: 'workflows.tpl.pipeline.name', descKey: 'workflows.tpl.pipeline.desc', agents_required: 2 },
  { type: 'research', nameKey: 'workflows.tpl.research.name', descKey: 'workflows.tpl.research.desc', agents_required: 3 },
  { type: 'approval', nameKey: 'workflows.tpl.approval.name', descKey: 'workflows.tpl.approval.desc', agents_required: 2 },
  { type: 'escalation', nameKey: 'workflows.tpl.escalation.name', descKey: 'workflows.tpl.escalation.desc', agents_required: 2 },
]

const DAG_ICONS: Record<TemplateType, string> = {
  pipeline:   '[ A ] → [ B ] → [ C ] → Output',
  research:   '[ A,B,C ] ⇒ fan-in → [ Synth ] → Output',
  approval:   '[ Draft ] → 🧑 Review → [ Publish ] → Output',
  escalation: '[ L1 ] →? [ L2 ] →? [ L3 ] →? 🧑 Human',
}

const STORAGE_PREFIX = 'agentos.wf.'
const RECENT_RUNS_KEY = STORAGE_PREFIX + 'runs'

function loadPersisted<T>(key: string, fallback: T): T {
  try { return JSON.parse(sessionStorage.getItem(STORAGE_PREFIX + key) || 'null') ?? fallback } catch { return fallback }
}
function savePersisted(key: string, value: unknown) {
  try { sessionStorage.setItem(STORAGE_PREFIX + key, JSON.stringify(value)) } catch { /* ignore */ }
}

export default function Workflows() {
  const { t } = useTranslation()
  const [agents, setAgents] = useState<Agent[]>([])
  const [selectedType, setSelectedType] = useState<TemplateType | null>(
    () => loadPersisted('type', null))
  const [selectedAgents, setSelectedAgents] = useState<string[]>(
    () => loadPersisted('agents', []))
  const [inputData, setInputData] = useState(
    () => loadPersisted('input', ''))
  const [running, setRunning] = useState(false)
  const [runProgress, setRunProgress] = useState('')
  const [runResult, setRunResult] = useState<string | null>(null)
  const [runError, setRunError] = useState<string | null>(null)
  const [runOutput, setRunOutput] = useState<string | null>(null)
  const [recentRuns, setRecentRuns] = useState<any[]>(() => {
    try { return JSON.parse(localStorage.getItem(RECENT_RUNS_KEY) || '[]') } catch { return [] }
  })

  useEffect(() => { agentsApi.list().then(setAgents).catch(() => {}) }, [])
  useEffect(() => { savePersisted('type', selectedType) }, [selectedType])
  useEffect(() => { savePersisted('agents', selectedAgents) }, [selectedAgents])
  useEffect(() => { savePersisted('input', inputData) }, [inputData])

  const runningAgents = agents.filter(a => a.status === 'running')
  const tpl = TEMPLATES.find(x => x.type === selectedType)

  function toggleAgent(name: string) {
    setSelectedAgents(prev =>
      prev.includes(name) ? prev.filter(n => n !== name) : [...prev, name])
  }

  async function handleRunWorkflow() {
    if (!selectedType || running) return
    setRunning(true); setRunResult(null); setRunError(null); setRunOutput(null)
    setRunProgress(`Starting ${selectedType} workflow with ${selectedAgents.length} agents...`)

    try {
      const res = await workflowsApi.run({
        workflow_name: selectedType,
        input_data: inputData,
        agent_names: selectedAgents,
        parameters: {},
      })

      if (res.steps_completed?.length) {
        setRunProgress(
          `${res.steps_completed.length} step(s) completed: ${res.steps_completed.join(' → ')}`)
      }

      if (res.output) setRunOutput(res.output)
      setRunResult(`${res.status.toUpperCase()}: ${res.steps_completed?.length || 0} steps`)

      setRecentRuns(prev => {
        const next = [{
          id: res.workflow_id, workflow: selectedType, status: res.status,
          steps: res.steps_completed?.length || 0, time: new Date().toLocaleTimeString(),
        }, ...prev].slice(0, 20)
        localStorage.setItem(RECENT_RUNS_KEY, JSON.stringify(next))
        return next
      })
    } catch (err) {
      setRunError(err instanceof Error ? err.message : 'Failed to run workflow')
    } finally {
      setRunning(false)
      setRunProgress('')
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t('workflows.title')}</h1>
        <p className="text-sm text-gray-500 mt-1">{t('workflows.subtitle')}</p>
      </div>

      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">{t('workflows.templates')}</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {TEMPLATES.map(tpl => (
            <div key={tpl.type} onClick={() => { setSelectedType(tpl.type); setRunResult(null); setRunError(null); setRunOutput(null) }}
              className={clsx('bg-white border rounded-lg p-5 cursor-pointer transition-all',
                selectedType === tpl.type ? 'border-blue-500 ring-2 ring-blue-100' : 'border-gray-200 hover:shadow-sm')}>
              <div className="flex items-center gap-3 mb-2">
                <div className="bg-blue-50 p-2 rounded-lg"><GitBranch className="w-5 h-5 text-blue-600" /></div>
                <div>
                  <h3 className="font-semibold text-gray-900">{t(tpl.nameKey as Parameters<typeof t>[0])}</h3>
                  <span className="text-xs text-gray-400">{t('workflows.agentsRequired', tpl.agents_required)}</span>
                </div>
              </div>
              <p className="text-sm text-gray-600">{t(tpl.descKey as Parameters<typeof t>[0])}</p>
              <div className="mt-3 flex items-center gap-1 text-xs text-gray-400">{DAG_ICONS[tpl.type]}</div>
            </div>
          ))}
        </div>
      </div>

      {selectedType && (
        <div className="bg-white border border-blue-200 rounded-lg p-5 space-y-4">
          <div className="flex items-center gap-2">
            <GitBranch className="w-5 h-5 text-blue-600" />
            <h2 className="font-semibold text-gray-900">{t(tpl!.nameKey as Parameters<typeof t>[0])}</h2>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Select agents ({selectedAgents.length} selected, need {tpl?.agents_required}+)
            </label>
            {runningAgents.length === 0 ? (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-700 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4" />
                No running agents. Start agents from the Agents page first.
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {runningAgents.map(a => (
                  <button key={a.agent_id} onClick={() => toggleAgent(a.name)}
                    className={clsx('flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm border transition-colors',
                      selectedAgents.includes(a.name)
                        ? 'bg-blue-50 border-blue-300 text-blue-700'
                        : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100')}>
                    <Bot className="w-3.5 h-3.5" />{a.name}
                    <span className="text-xs text-gray-400">({a.provider})</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Input data / prompt</label>
            <textarea rows={2} value={inputData} onChange={e => setInputData(e.target.value)}
              placeholder="Enter workflow input..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
          </div>

          {/* Run button + status */}
          <div className="space-y-3">
            <div className="flex items-center gap-4">
              <button onClick={handleRunWorkflow} disabled={running || selectedAgents.length < (tpl?.agents_required || 1)}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 inline-flex items-center gap-2">
                {running && <Loader2 className="w-4 h-4 animate-spin" />}
                {running ? t('common.loading') : t('workflows.runBtn')}
              </button>
              {running && runProgress && (
                <span className="text-sm text-gray-500 flex items-center gap-1">
                  <Clock className="w-4 h-4 text-gray-400" />{runProgress}
                </span>
              )}
            </div>
            {runResult && (
              <div className="flex items-center gap-2 text-sm text-green-600 bg-green-50 rounded-lg py-2 px-3">
                <CheckCircle className="w-4 h-4" />{runResult}
              </div>
            )}
            {runError && (
              <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 rounded-lg py-2 px-3">
                <AlertTriangle className="w-4 h-4" />{runError}
              </div>
            )}
            {/* Workflow output */}
            {runOutput && (
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-sm text-gray-700 whitespace-pre-wrap max-h-64 overflow-y-auto">
                {runOutput}
              </div>
            )}
          </div>
        </div>
      )}

      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">{t('workflows.recentRuns')}</h2>
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 text-xs uppercase">
              <tr>
                <th className="px-4 py-3 text-left">{t('workflows.colWorkflow')}</th>
                <th className="px-4 py-3 text-left">{t('workflows.colStatus')}</th>
                <th className="px-4 py-3 text-left">{t('workflows.colSteps')}</th>
                <th className="px-4 py-3 text-left">{t('workflows.colDuration')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {recentRuns.length === 0 ? (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-gray-400">{t('workflows.noRuns')}</td></tr>
              ) : (
                recentRuns.map((r, i) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium capitalize">{r.workflow}</td>
                    <td className="px-4 py-3">
                      <span className={clsx('px-2 py-0.5 rounded-full text-xs font-medium',
                        r.status === 'completed' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700')}>
                        {r.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500">{r.steps}</td>
                    <td className="px-4 py-3 text-gray-400">{r.time}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
