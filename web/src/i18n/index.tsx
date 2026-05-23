import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { en, type TranslationKey } from './locales/en'
import { zh } from './locales/zh'

export type Locale = 'en' | 'zh'

const DICTIONARIES: Record<Locale, Record<TranslationKey, string>> = {
  en,
  zh,
}

const STORAGE_KEY = 'agentos.locale'

interface I18nContextValue {
  locale: Locale
  setLocale: (locale: Locale) => void
  t: (key: TranslationKey, ...args: (string | number)[]) => string
}

const I18nContext = createContext<I18nContextValue | null>(null)

function detectDefaultLocale(): Locale {
  const stored = typeof localStorage !== 'undefined' ? localStorage.getItem(STORAGE_KEY) : null
  if (stored === 'zh' || stored === 'en') return stored
  const browserLang = typeof navigator !== 'undefined' ? navigator.language : 'en'
  return browserLang.toLowerCase().startsWith('zh') ? 'zh' : 'en'
}

function format(template: string, args: (string | number)[]): string {
  return args.reduce<string>(
    (acc, val, idx) => acc.split(`{${idx}}`).join(String(val)),
    template,
  )
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => detectDefaultLocale())

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next)
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch { /* ignore */ }
    if (typeof document !== 'undefined') {
      document.documentElement.lang = next === 'zh' ? 'zh-CN' : 'en'
    }
  }, [])

  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.documentElement.lang = locale === 'zh' ? 'zh-CN' : 'en'
    }
  }, [locale])

  const t = useCallback(
    (key: TranslationKey, ...args: (string | number)[]): string => {
      const dict = DICTIONARIES[locale]
      const template = dict[key] ?? en[key] ?? key
      return args.length > 0 ? format(template, args) : template
    },
    [locale],
  )

  const value = useMemo<I18nContextValue>(() => ({ locale, setLocale, t }), [locale, setLocale, t])
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useTranslation(): I18nContextValue {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useTranslation must be used within <I18nProvider>')
  return ctx
}
