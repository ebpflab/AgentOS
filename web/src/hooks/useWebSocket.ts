/**
 * WebSocket hook for real-time event streaming from AgentOS.
 *
 * Uses a **global singleton** connection shared by all components.
 * Reconnects with exponential backoff on failure.
 */
import { useCallback, useRef, useSyncExternalStore } from 'react'

export interface AgentOSEvent {
  event_id: string
  topic: string
  data: unknown
  timestamp: number
  source: string
}

// ─── Global singleton ────────────────────────────────────────────

const MAX_EVENTS = 200
const MAX_RECONNECT_DELAY = 30_000
const INITIAL_RECONNECT_DELAY = 2_000

let _ws: WebSocket | null = null
let _connected = false
let _events: AgentOSEvent[] = []
let _attempt = 0
let _timer: ReturnType<typeof setTimeout> | undefined
let _refCount = 0

const _listeners = new Set<() => void>()

function _notify() {
  _listeners.forEach(fn => fn())
}

function _connect() {
  if (_ws?.readyState === WebSocket.OPEN || _ws?.readyState === WebSocket.CONNECTING) return

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const ws = new WebSocket(`${protocol}//${window.location.host}/ws/events`)

  ws.onopen = () => {
    _connected = true
    _attempt = 0
    ws.send(JSON.stringify({ type: 'subscribe', patterns: ['*'] }))
    _notify()
  }

  ws.onmessage = (e) => {
    try {
      const event: AgentOSEvent = JSON.parse(e.data)
      _events = [event, ..._events].slice(0, MAX_EVENTS)
      _notify()
    } catch { /* ignore non-JSON */ }
  }

  ws.onclose = () => {
    _ws = null
    _connected = false
    _notify()
    if (_refCount > 0) {
      const delay = Math.min(INITIAL_RECONNECT_DELAY * Math.pow(2, _attempt), MAX_RECONNECT_DELAY)
      _attempt += 1
      _timer = setTimeout(_connect, delay)
    }
  }

  ws.onerror = () => ws.close()

  _ws = ws
}

function _disconnect() {
  clearTimeout(_timer)
  if (_ws) {
    _ws.onclose = null
    _ws.close()
    _ws = null
  }
  _connected = false
  _notify()
}

function _subscribe(listener: () => void) {
  _listeners.add(listener)
  _refCount++
  if (_refCount === 1) _connect()
  return () => {
    _listeners.delete(listener)
    _refCount--
    if (_refCount <= 0) {
      _refCount = 0
      _disconnect()
    }
  }
}

function _getConnectedSnapshot() { return _connected }
function _getEventsSnapshot() { return _events }

// ─── React hook ──────────────────────────────────────────────────

interface UseWebSocketOptions {
  patterns?: string[]
  maxEvents?: number
  autoConnect?: boolean
}

export function useWebSocket(_options: UseWebSocketOptions = {}) {
  const connected = useSyncExternalStore(_subscribe, _getConnectedSnapshot)
  const allEvents = useSyncExternalStore(_subscribe, _getEventsSnapshot)

  const { patterns } = _options
  const patternsRef = useRef(patterns)
  patternsRef.current = patterns

  // Filter events by pattern if caller specified non-default patterns
  const events = (!patterns || (patterns.length === 1 && patterns[0] === '*'))
    ? allEvents
    : allEvents.filter(e => {
        return patternsRef.current!.some(p => {
          if (p === '*') return true
          // Simple fnmatch: "agent.*" matches "agent.created"
          const re = new RegExp('^' + p.replace(/\./g, '\\.').replace(/\*/g, '.*') + '$')
          return re.test(e.topic)
        })
      })

  const clearEvents = useCallback(() => { _events = []; _notify() }, [])

  return { events, connected, connect: _connect, disconnect: _disconnect, clearEvents }
}
