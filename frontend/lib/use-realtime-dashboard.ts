/**
 * G+2: Real-time dashboard WebSocket hook.
 *
 * Holding-scoped event stream. Bağlanma + reconnect (exponential backoff)
 * + heartbeat + lifecycle cleanup tek noktada.
 *
 * Kullanım:
 *   const { events, status } = useRealtimeDashboard({ holdingId: 1 });
 *
 *   useEffect(() => {
 *     const latest = events[events.length - 1];
 *     if (latest?.event_type === "balance.updated") {
 *       setBalance(latest.payload.total);
 *     }
 *   }, [events]);
 *
 * Tasarım:
 *  - Reconnect: exponential backoff (1s, 2s, 4s, 8s, max 30s)
 *  - Heartbeat: her 25s'de "ping" gönderir, "pong" alır
 *  - Token auth: localStorage'dan veya prop'tan alır
 *  - Cleanup: component unmount'ta close + interval clear
 *  - SSR-safe: window/WebSocket sadece useEffect içinde
 *
 * Event envelope (G+2 backend ile sözleşme):
 *   { event_type: string, holding_id: number, timestamp: number, payload: object }
 */
import { useEffect, useRef, useState, useCallback } from "react";
import { getApiBaseUrl, getToken } from "@/lib/api";

export interface RealtimeEvent {
  event_type: string;
  holding_id: number;
  timestamp: number;
  payload: Record<string, unknown>;
}

export type ConnectionStatus =
  | "idle"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "disconnected"
  | "error";

interface UseRealtimeDashboardOptions {
  holdingId: number;
  /** Override default token (otherwise localStorage). */
  token?: string;
  /** Max event buffer size (default 200). */
  maxEvents?: number;
  /** Disable real-time (e.g. during SSR or auth pending). */
  enabled?: boolean;
}

interface UseRealtimeDashboardResult {
  events: RealtimeEvent[];
  status: ConnectionStatus;
  reconnect: () => void;
}

const HEARTBEAT_INTERVAL_MS = 25_000;
const RECONNECT_INITIAL_MS = 1_000;
const RECONNECT_MAX_MS = 30_000;

function buildWsUrl(holdingId: number, token: string): string {
  // HTTP base URL'i WS protokolüne çevir (http→ws, https→wss)
  const httpBase = getApiBaseUrl();
  const wsBase = httpBase.replace(/^http/, "ws");
  return `${wsBase}/api/v1/ws/holdings/${holdingId}/dashboard?token=${encodeURIComponent(token)}`;
}

export function useRealtimeDashboard({
  holdingId,
  token,
  maxEvents = 200,
  enabled = true,
}: UseRealtimeDashboardOptions): UseRealtimeDashboardResult {
  const [events, setEvents] = useState<RealtimeEvent[]>([]);
  const [status, setStatus] = useState<ConnectionStatus>("idle");

  const wsRef = useRef<WebSocket | null>(null);
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const manuallyClosedRef = useRef(false);

  const cleanup = useCallback(() => {
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (wsRef.current) {
      manuallyClosedRef.current = true;
      try {
        wsRef.current.close();
      } catch {
        // ignore close errors
      }
      wsRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (typeof window === "undefined") return; // SSR guard
    const authToken = token ?? getToken();
    if (!authToken) {
      setStatus("error");
      return;
    }

    setStatus(reconnectAttemptsRef.current > 0 ? "reconnecting" : "connecting");
    manuallyClosedRef.current = false;

    let ws: WebSocket;
    try {
      ws = new WebSocket(buildWsUrl(holdingId, authToken));
    } catch {
      setStatus("error");
      return;
    }
    wsRef.current = ws;

    ws.onopen = () => {
      reconnectAttemptsRef.current = 0;
      setStatus("connected");
      // Heartbeat — backend "ping" → "pong" pattern
      heartbeatRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          try {
            ws.send("ping");
          } catch {
            // ignore — onclose handles
          }
        }
      }, HEARTBEAT_INTERVAL_MS);
    };

    ws.onmessage = (e) => {
      // "pong" heartbeat reply — sayılmaz
      if (e.data === "pong") return;
      try {
        const parsed = JSON.parse(e.data) as RealtimeEvent;
        if (parsed && typeof parsed.event_type === "string") {
          setEvents((prev) => {
            const next = [...prev, parsed];
            // Buffer overflow → en eskileri at
            if (next.length > maxEvents) {
              return next.slice(-maxEvents);
            }
            return next;
          });
        }
      } catch {
        // malformed event ignored
      }
    };

    ws.onerror = () => {
      // onerror → onclose her zaman tetiklenir, reconnect orada
    };

    ws.onclose = () => {
      if (heartbeatRef.current) {
        clearInterval(heartbeatRef.current);
        heartbeatRef.current = null;
      }
      wsRef.current = null;
      if (manuallyClosedRef.current) {
        setStatus("disconnected");
        return;
      }
      // Reconnect exponential backoff
      const attempt = reconnectAttemptsRef.current;
      const delay = Math.min(
        RECONNECT_INITIAL_MS * Math.pow(2, attempt),
        RECONNECT_MAX_MS,
      );
      reconnectAttemptsRef.current = attempt + 1;
      setStatus("reconnecting");
      reconnectTimerRef.current = setTimeout(connect, delay);
    };
  }, [holdingId, token, maxEvents]);

  // Manual reconnect helper
  const reconnect = useCallback(() => {
    cleanup();
    reconnectAttemptsRef.current = 0;
    connect();
  }, [cleanup, connect]);

  useEffect(() => {
    if (!enabled) {
      cleanup();
      setStatus("idle");
      return;
    }
    connect();
    return cleanup;
  }, [enabled, connect, cleanup]);

  return { events, status, reconnect };
}
