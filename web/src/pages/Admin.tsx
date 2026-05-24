import { useEffect, useState } from 'react'
import { Shield, Users, Key, Cpu, CheckCircle, AlertTriangle } from 'lucide-react'
import { adminApi } from '../lib/api'
import type { RolesMap, ProviderInfo, ProviderUpdateRequest } from '../lib/api'
import { useTranslation } from '../i18n'

export default function Admin() {
  const { t } = useTranslation()
  const [roles, setRoles] = useState<RolesMap | null>(null)
  const [providers, setProviders] = useState<ProviderInfo[]>([])
  const [editingProvider, setEditingProvider] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState<{ ok: boolean; text: string } | null>(null)

  useEffect(() => {
    adminApi.roles().then(setRoles).catch(() => {})
    loadProviders()
  }, [])

  async function loadProviders() {
    try { setProviders(await adminApi.providers()) } catch { /* API not running */ }
  }

  async function handleSaveProvider(name: string, data: ProviderUpdateRequest) {
    setSaving(true)
    setSaveMsg(null)
    try {
      await adminApi.updateProvider(name, data)
      setSaveMsg({ ok: true, text: t('admin.providerSaved') })
      setEditingProvider(null)
      loadProviders()
    } catch {
      setSaveMsg({ ok: false, text: t('admin.providerSaveError') })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t('admin.title')}</h1>
        <p className="text-sm text-gray-500 mt-1">{t('admin.subtitle')}</p>
      </div>

      {/* Tenants + RBAC */}
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

      {/* Provider Configuration */}
      <div className="bg-white border border-gray-200 rounded-lg">
        <div className="px-5 py-4 border-b border-gray-200 flex items-center gap-2">
          <Cpu className="w-5 h-5 text-gray-400" />
          <h2 className="font-semibold text-gray-900">{t('admin.providers')}</h2>
        </div>
        <div className="p-5">
          {saveMsg && (
            <div className={`flex items-center gap-2 text-sm px-4 py-3 rounded-lg mb-4 ${
              saveMsg.ok ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
            }`}>
              {saveMsg.ok ? <CheckCircle className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
              {saveMsg.text}
            </div>
          )}

          {providers.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-4">{t('common.loading')}</p>
          ) : (
            <div className="space-y-4">
              {providers.map(provider => (
                <ProviderCard
                  key={provider.name}
                  provider={provider}
                  isEditing={editingProvider === provider.name}
                  saving={saving}
                  onEdit={() => {
                    setEditingProvider(editingProvider === provider.name ? null : provider.name)
                    setSaveMsg(null)
                  }}
                  onSave={(data) => handleSaveProvider(provider.name, data)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Security Overview */}
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

function ProviderCard({
  provider, isEditing, saving, onEdit, onSave,
}: {
  provider: ProviderInfo
  isEditing: boolean
  saving: boolean
  onEdit: () => void
  onSave: (data: ProviderUpdateRequest) => void
}) {
  const { t } = useTranslation()
  const [form, setForm] = useState<ProviderUpdateRequest>({})

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    onSave(form)
  }

  return (
    <div className="border border-gray-200 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="bg-indigo-50 p-2 rounded-lg">
            <Cpu className="w-5 h-5 text-indigo-600" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900 capitalize">{provider.name}</h3>
            <span className={`text-xs font-medium ${
              provider.enabled ? 'text-green-600' : 'text-gray-400'
            }`}>
              {provider.enabled ? t('admin.providerEnabled') : t('admin.providerDisabled')}
              {' · '}
              {provider.default_model}
            </span>
          </div>
        </div>
        <button
          onClick={onEdit}
          className="text-xs px-3 py-1.5 border border-gray-300 rounded-lg hover:bg-gray-50"
        >
          {isEditing ? t('common.cancel') : t('admin.providerSave')}
        </button>
      </div>

      {isEditing && (
        <form onSubmit={handleSubmit} className="space-y-3 pt-3 border-t border-gray-100">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {/* Model dropdown */}
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                {t('admin.providerModel')}
              </label>
              <select
                defaultValue={provider.default_model}
                onChange={e => setForm(f => ({ ...f, default_model: e.target.value }))}
                className="w-full px-2.5 py-1.5 border border-gray-300 rounded text-sm bg-white"
              >
                {provider.models.map(m => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>

            {/* API Key */}
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                {t('admin.providerApiKey')}
              </label>
              <input
                type="password"
                defaultValue=""
                onChange={e => setForm(f => ({ ...f, api_key: e.target.value }))}
                className="w-full px-2.5 py-1.5 border border-gray-300 rounded text-sm"
                placeholder={provider.api_key_set ? '•••••••• (unchanged)' : 'sk-...'}
              />
            </div>

            {/* API Base URL — only for OpenAI (Azure) and Ollama */}
            {provider.name === 'ollama' && (
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  {t('admin.providerBaseUrl')}
                </label>
                <input
                  defaultValue={provider.base_url}
                  onChange={e => setForm(f => ({ ...f, base_url: e.target.value }))}
                  className="w-full px-2.5 py-1.5 border border-gray-300 rounded text-sm"
                  placeholder="http://localhost:11434"
                />
              </div>
            )}
            {provider.name === 'openai' && (
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  {t('admin.providerApiBase')} (Azure)
                </label>
                <input
                  defaultValue={provider.api_base}
                  onChange={e => setForm(f => ({ ...f, api_base: e.target.value }))}
                  className="w-full px-2.5 py-1.5 border border-gray-300 rounded text-sm"
                  placeholder="https://api.openai.com"
                />
              </div>
            )}
            {provider.name === 'anthropic' && (
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  {t('admin.providerApiBase')}
                </label>
                <input
                  defaultValue={provider.api_base}
                  onChange={e => setForm(f => ({ ...f, api_base: e.target.value }))}
                  className="w-full px-2.5 py-1.5 border border-gray-300 rounded text-sm"
                  placeholder="https://api.anthropic.com"
                />
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 pt-1">
            <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
              <input
                type="checkbox"
                defaultChecked={provider.enabled}
                onChange={e => setForm(f => ({ ...f, enabled: e.target.checked }))}
                className="rounded"
              />
              {t('admin.providerEnabled')}
            </label>
          </div>

          <button
            type="submit"
            disabled={saving}
            className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? t('common.loading') : t('admin.providerSave')}
          </button>
        </form>
      )}
    </div>
  )
}
