import { MessageSquare } from 'lucide-react'
import { useTranslation } from '../i18n'

export default function Sessions() {
  const { t } = useTranslation()
  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t('sessions.title')}</h1>
        <p className="text-sm text-gray-500 mt-1">{t('sessions.subtitle')}</p>
      </div>
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-500 text-xs uppercase">
            <tr>
              <th className="px-4 py-3 text-left">{t('sessions.colId')}</th>
              <th className="px-4 py-3 text-left">{t('sessions.colAgent')}</th>
              <th className="px-4 py-3 text-left">{t('sessions.colMessages')}</th>
              <th className="px-4 py-3 text-left">{t('sessions.colStatus')}</th>
              <th className="px-4 py-3 text-left">{t('sessions.colCreated')}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td colSpan={5} className="px-4 py-12 text-center text-gray-400">
                <MessageSquare className="w-10 h-10 mx-auto mb-3 text-gray-300" />
                <p className="font-medium text-gray-500">{t('sessions.empty')}</p>
                <p className="text-sm mt-1">{t('sessions.emptyHint')}</p>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}
