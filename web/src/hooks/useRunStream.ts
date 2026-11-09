import { useEffect, useState } from 'react';
import { api } from '../api/client';

export interface StreamEvent {
  id: string;
  timestamp: string;
  raw: string;
  type: 'tool' | 'thought' | 'stdout' | 'info' | 'error';
  toolName?: string;
  summary?: string;
}

export function useRunStream(runId: string | null, enabled = true) {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId || !enabled) {
      setEvents([]);
      setIsConnected(false);
      return;
    }

    const url = api.getRunStreamUrl(runId);
    let eventSource: EventSource | null = null;
    let eventCounter = 0;

    try {
      eventSource = new EventSource(url);

      eventSource.onopen = () => {
        setIsConnected(true);
        setError(null);
      };

      eventSource.onmessage = (e) => {
        const line = e.data?.trim();
        if (!line) return;

        eventCounter += 1;
        let type: StreamEvent['type'] = 'stdout';
        let toolName: string | undefined;
        let summary: string | undefined;

        try {
          if (line.startsWith('{') && line.endsWith('}')) {
            const parsed = JSON.parse(line);
            const su = parsed.step_update || {};
            if (su.step_type === 'tool') {
              type = 'tool';
              toolName = su.tool_name;
              const params = su.tool_info?.parameters || {};
              summary = params.CommandLine || params.command || params.Path || params.path || '';
            } else if (parsed.event === 'agent_response' || su.step_type === 'model_response') {
              type = 'thought';
              summary = parsed.content || su.content || '';
            }
          }
        } catch {
          // not json
        }

        const newEvent: StreamEvent = {
          id: `${runId}-${eventCounter}-${Date.now()}`,
          timestamp: new Date().toLocaleTimeString(),
          raw: line,
          type,
          toolName,
          summary,
        };

        setEvents((prev) => [...prev.slice(-300), newEvent]); // Keep latest 300 lines
      };

      eventSource.onerror = () => {
        setIsConnected(false);
        // EventSource will automatically attempt reconnection
      };
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to connect stream');
      setIsConnected(false);
    }

    return () => {
      if (eventSource) {
        eventSource.close();
      }
      setIsConnected(false);
    };
  }, [runId, enabled]);

  const clear = () => setEvents([]);

  return {
    events,
    isConnected,
    error,
    clear,
  };
}
