/**
 * WebSocket hook for real-time event streaming from AgentOS.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

export interface AgentOSEvent {
  event_id: string
  topic: string
  data: unknown
  timestamp: number
  source: string
}

interface UseWebSocketOptions {
  patterns?: string[]
  maxEvents?: number
  autoConnect?: boolean
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const { patterns = ['*'], maxEvents = 200, autoConnect = true } = options
  const [events, setEvents] = useState<AgentOSEvent[]>([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>()

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/events`)

    ws.onopen = () => {
      setConnected(true)
      // Subscribe to patterns
      ws.send(JSON.stringify({ type: 'subscribe', patterns }))
    }

    ws.onmessage = (e) => {
      try {
        const event: AgentOSEvent = JSON.parse(e.data)
        setEvents(prev => {
          const next = [event, ...prev]
          return next.length > maxEvents ? next.slice(0, maxEvents) : next
        })
      } catch {
        // Ignore non-JSON messages
      }
    }

    ws.onclose = () => {
      setConnected(false)
      // Auto-reconnect after 3s
      reconnectTimerRef.current = setTimeout(connect, 3000)
    }

    ws.onerror = () => {
      ws.close()
    }

    wsRef.current = ws
  }, [patterns, maxEvents])

  const disconnect = useCallback(() => {
    clearTimeout(reconnectTimerRef.current)
    wsRef.current?.close()
    wsRef.current = null
    setConnected(false)
  }, [])

  const clearEvents = useCallback(() => setEvents([]), [])

  useEffect(() => {
    if (autoConnect) connect()
    return () => disconnect()
  }, [autoConnect, connect, disconnect])

  return { events, connected, connect, disconnect, clearEvents }
}
