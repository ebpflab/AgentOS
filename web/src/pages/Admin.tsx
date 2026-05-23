import { useEffect, useState } from 'react'
import { Shield, Users, Key } from 'lucide-react'
import { adminApi } from '../lib/api'
import type { RolesMap } from '../lib/api'
import { useTranslation } from '../i18n'

export default function Admin() {
  const { t } = useTranslation()
  const [roles, setRoles] = useState<RolesMap | null>(null)

  useEffect(() => { adminApi.roles().then(setRoles).catch(() => {}) }, [])

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t('admin.title')}</h1>
        <p className="text-sm text-gray-500 mt-1">{t('admin.subtitle')}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white border border-gray-200 rounded-lg">
          <div className="px-5 py-4 border-b border-gray-200 flex items-center gap-2">
            <Users className="w-5 h-5 text-gray-400" />
            <h2 className="font-semibold text-gray-900">{t('admin.tenants')}</h2>
          </div>
          <div className="p-5">
            <div className="bg-gray-50 rounded-lg p-4 text-center text-gray-500 text-sm">
              <Users className="w-8 h-8 mx-auto mb-2 text-gray-300" />
              <p>{t('admin.tenantsHint')}</p>
              <p className="text-xs text-gray-400 mt-1">{t('admin.defaultTenant')}</p>
            </div>
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg">
          <div className="px-5 py-4 border-b border-gray-200 flex items-center gap-2">
            <Key className="w-5 h-5 text-gray-400" />
            <h2 className="font-semibold text-gray-900">{t('admin.rbac')}</h2>
          </div>
          <div className="p-5">
            {roles ? (
              <div className="space-y-4">
                {Object.entries(roles).map(([role, permissions]) => (
                  <div key={role}>
                    <div className="flex items-center gap-2 mb-1.5">
                      <Shield className="w-4 h-4 text-blue-500" />
                      <span className="font-medium text-gray-900 capitalize">{role}</span>
                      <span className="text-xs text-gray-400">{t('admin.permsCount', permissions.length)}</span>
                    </div>
                    <div className="flex flex-wrap gap-1.5 ml-6">
                      {permissions.map(perm => (
                        <span key={perm} className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded text-xs font-mono">
                          {perm}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : <p className="text-sm text-gray-400">{t('admin.loadingRoles')}</p>}
          </div>
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <h2 className="font-semibold text-gray-900 mb-3">{t('admin.securityTitle')}</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
          <div className="bg-gray-50 rounded-lg p-4">
            <p className="text-gray-500">{t('admin.authn')}</p>
            <p className="font-medium text-gray-900 mt-1">{t('admin.authnVal')}</p>
            <p className="text-xs text-gray-400 mt-0.5">{t('admin.authnSub')}</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-4">
            <p className="text-gray-500">{t('admin.authz')}</p>
            <p className="font-medium text-gray-900 mt-1">{t('admin.authzVal')}</p>
            <p className="text-xs text-gray-400 mt-0.5">{t('admin.authzSub')}</p>
          </div>
          <div className="bg-gray-50 rounded-lg p-4">
            <p className="text-gray-500">{t('admin.audit')}</p>
            <p className="font-medium text-gray-900 mt-1">{t('admin.auditVal')}</p>
            <p className="text-xs text-gray-400 mt-0.5">{t('admin.auditSub')}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
