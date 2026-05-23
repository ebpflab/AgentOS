import { Link, Outlet, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, Bot, GitBranch, MessageSquare,
  BarChart3, Shield, Activity, Languages,
} from 'lucide-react'
import clsx from 'clsx'
import { useWebSocket } from '../hooks/useWebSocket'
import { useTranslation, type Locale } from '../i18n'

type NavItem = { path: string; labelKey: string; icon: React.ElementType }

const NAV_ITEMS: NavItem[] = [
  { path: '/',          labelKey: 'nav.dashboard',  icon: LayoutDashboard },
  { path: '/agents',    labelKey: 'nav.agents',     icon: Bot             },
  { path: '/workflows', labelKey: 'nav.workflows',  icon: GitBranch       },
  { path: '/sessions',  labelKey: 'nav.sessions',   icon: MessageSquare   },
  { path: '/metrics',   labelKey: 'nav.metrics',    icon: BarChart3       },
  { path: '/admin',     labelKey: 'nav.admin',      icon: Shield          },
]

const LOCALE_OPTIONS: { value: Locale; label: string }[] = [
  { value: 'en', label: 'EN' },
  { value: 'zh', label: '中' },
]

export default function Layout() {
  const location = useLocation()
  const { connected } = useWebSocket({ autoConnect: true })
  const { t, locale, setLocale } = useTranslation()

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-60 bg-gray-900 text-white flex flex-col shrink-0">
        {/* Logo */}
        <div className="h-16 flex items-center px-5 border-b border-gray-800">
          <Bot className="w-7 h-7 text-blue-400 mr-2.5" />
          <span className="text-lg font-bold tracking-tight">AgentOS</span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 px-3 space-y-1">
          {NAV_ITEMS.map(({ path, labelKey, icon: Icon }) => {
            const active = path === '/'
              ? location.pathname === '/'
              : location.pathname.startsWith(path)
            return (
              <Link
                key={path}
                to={path}
                className={clsx(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                  active
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                )}
              >
                <Icon className="w-5 h-5 shrink-0" />
                {t(labelKey as Parameters<typeof t>[0])}
              </Link>
            )
          })}
        </nav>

        {/* Language switcher + Status */}
        <div className="px-5 py-4 border-t border-gray-800 space-y-3">
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <Languages className="w-3.5 h-3.5 shrink-0" />
            <span>{t('layout.language')}</span>
            <div className="ml-auto flex rounded-md overflow-hidden border border-gray-700">
              {LOCALE_OPTIONS.map(({ value, label }) => (
                <button
                  key={value}
                  onClick={() => setLocale(value)}
                  className={clsx(
                    'px-2.5 py-1 text-xs font-medium transition-colors',
                    locale === value
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-400 hover:bg-gray-700 hover:text-white'
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <Activity className={clsx('w-3.5 h-3.5', connected ? 'text-green-400' : 'text-red-400')} />
            {connected ? t('layout.connected') : t('layout.disconnected')}
          </div>
          <div className="text-xs text-gray-500">{t('layout.version')}</div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto bg-gray-50">
        <Outlet />
      </main>
    </div>
  )
}
