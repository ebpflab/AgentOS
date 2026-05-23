import { useState } from 'react'
import { GitBranch } from 'lucide-react'
import clsx from 'clsx'
import { useTranslation } from '../i18n'

type TemplateType = 'pipeline' | 'research' | 'approval' | 'escalation'

interface WorkflowTemplate {
  type: TemplateType
  nameKey: string
  descKey: string
  agents_required: number
}

const TEMPLATES: WorkflowTemplate[] = [
  { type: 'pipeline',   nameKey: 'workflows.tpl.pipeline.name',   descKey: 'workflows.tpl.pipeline.desc',   agents_required: 2 },
  { type: 'research',   nameKey: 'workflows.tpl.research.name',   descKey: 'workflows.tpl.research.desc',   agents_required: 3 },
  { type: 'approval',   nameKey: 'workflows.tpl.approval.name',   descKey: 'workflows.tpl.approval.desc',   agents_required: 2 },
  { type: 'escalation', nameKey: 'workflows.tpl.escalation.name', descKey: 'workflows.tpl.escalation.desc', agents_required: 2 },
]

const DAG_ICONS: Record<TemplateType, string> = {
  pipeline:   '[ A ] → [ B ] → [ C ] → Output',
  research:   '[ A,B,C ] ⇒ fan-in → [ Synth ] → Output',
  approval:   '[ Draft ] → 🧑 Review → [ Publish ] → Output',
  escalation: '[ L1 ] →? [ L2 ] →? [ L3 ] →? 🧑 Human',
}

export default function Workflows() {
  const { t } = useTranslation()
  const [selectedType, setSelectedType] = useState<TemplateType | null>(null)

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
            <div key={tpl.type} onClick={() => setSelectedType(tpl.type)}
              className={clsx('bg-white border rounded-lg p-5 cursor-pointer transition-all',
                selectedType === tpl.type ? 'border-blue-500 ring-2 ring-blue-100' : 'border-gray-200 hover:shadow-sm')}>
              <div className="flex items-center gap-3 mb-2">
                <div className="bg-blue-50 p-2 rounded-lg">
                  <GitBranch className="w-5 h-5 text-blue-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">{t(tpl.nameKey as Parameters<typeof t>[0])}</h3>
                  <span className="text-xs text-gray-400">{t('workflows.agentsRequired', tpl.agents_required)}</span>
                </div>
              </div>
              <p className="text-sm text-gray-600">{t(tpl.descKey as Parameters<typeof t>[0])}</p>
              <div className="mt-3 flex items-center gap-1 text-xs text-gray-400">
                {DAG_ICONS[tpl.type]}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">{t('workflows.graph')}</h2>
        <div className="bg-white border border-gray-200 rounded-lg h-64 flex items-center justify-center text-gray-400">
          {selectedType ? (
            <div className="text-center">
              <GitBranch className="w-10 h-10 mx-auto mb-2 text-blue-300" />
              <p className="font-medium text-gray-600">
                {t(TEMPLATES.find(x => x.type === selectedType)!.nameKey as Parameters<typeof t>[0])}
              </p>
              <p className="text-sm">{t('workflows.dagHint')}</p>
              <button className="mt-3 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
                {t('workflows.runBtn')}
              </button>
            </div>
          ) : (
            <p className="text-sm">{t('workflows.selectTemplate')}</p>
          )}
        </div>
      </div>

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
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-gray-400">{t('workflows.noRuns')}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
