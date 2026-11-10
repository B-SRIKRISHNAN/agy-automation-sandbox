import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../api/client';
import type { ChatSession, ChatMessage, DraftIssue, CreateAndRunResponse } from '../api/types';

export function useChatSession(projectId?: string) {
  const [session, setSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draftIssue, setDraftIssue] = useState<DraftIssue | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [isTerminating, setIsTerminating] = useState(false);
  const [isCreatingAndRunning, setIsCreatingAndRunning] = useState(false);
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);

  // Close SSE connection
  const closeStream = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsStreaming(false);
    setActiveTool(null);
  }, []);

  // Connect to SSE stream
  const connectStream = useCallback((sessionId: string) => {
    closeStream();
    setIsStreaming(true);

    const streamUrl = api.getChatStreamUrl(sessionId);
    const es = new EventSource(streamUrl);
    eventSourceRef.current = es;

    let assistantText = '';

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);

        if (data.type === 'delta') {
          assistantText += data.delta;
          setActiveTool(null);
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.role === 'assistant') {
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...last,
                content: assistantText,
              };
              return updated;
            } else {
              return [
                ...prev,
                {
                  role: 'assistant',
                  content: assistantText,
                  timestamp: new Date().toISOString(),
                },
              ];
            }
          });
        } else if (data.type === 'tool') {
          setActiveTool(data.tool);
        } else if (data.type === 'draft_issue' && data.draft) {
          setDraftIssue(data.draft);
        } else if (data.type === 'result') {
          assistantText = data.response || assistantText;
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.role === 'assistant') {
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...last,
                content: assistantText,
              };
              return updated;
            }
            return prev;
          });
        } else if (data.type === 'done' || data.type === 'terminated') {
          closeStream();
          if (data.type === 'terminated') {
            setSession((prev) => (prev ? { ...prev, status: 'TERMINATED' } : null));
          }
        }
      } catch (err) {
        console.error('Failed to parse SSE event:', err);
      }
    };

    es.onerror = () => {
      closeStream();
    };
  }, [closeStream]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      closeStream();
    };
  }, [closeStream]);

  // Start new formulation chat session
  const startSession = async (initialPrompt: string = '') => {
    setIsStarting(true);
    setError(null);
    setMessages([]);
    setDraftIssue(null);
    try {
      const newSession = await api.createChatSession({
        project_id: projectId,
        initial_prompt: initialPrompt,
      });
      setSession(newSession);
      setMessages(newSession.messages);
      if (newSession.draft_issue) {
        setDraftIssue(newSession.draft_issue);
      }
      if (initialPrompt) {
        connectStream(newSession.session_id);
      }
      return newSession;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to start chat session';
      setError(msg);
      throw err;
    } finally {
      setIsStarting(false);
    }
  };

  // Send a follow-up message into turn
  const sendMessage = async (content: string) => {
    if (!session || session.status !== 'ACTIVE' || !content.trim()) return;
    setError(null);

    // Optimistically append user message
    const userMsg: ChatMessage = {
      role: 'user',
      content: content.trim(),
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      connectStream(session.session_id);
      await api.sendChatMessage(session.session_id, content.trim());
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to send message';
      setError(msg);
      closeStream();
    }
  };

  // Immediately terminate session
  const terminateSession = async () => {
    if (!session) return;
    setIsTerminating(true);
    closeStream();
    try {
      const updated = await api.terminateChatSession(session.session_id);
      setSession(updated);
    } catch (err) {
      console.error('Error terminating session:', err);
    } finally {
      setIsTerminating(false);
    }
  };

  // Convert draft into GitHub issue & launch runner
  const createAndRun = async (
    title: string,
    body: string,
    autoApprove: boolean = false,
    engine: string = 'auto'
  ): Promise<CreateAndRunResponse> => {
    if (!session) throw new Error('No active chat session');
    setIsCreatingAndRunning(true);
    closeStream();
    try {
      const res = await api.createAndRunFromChat(session.session_id, {
        title,
        body,
        auto_approve: autoApprove,
        engine,
      });
      setSession((prev) => (prev ? { ...prev, status: 'CONVERTED' } : null));
      return res;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to create and start issue';
      setError(msg);
      throw err;
    } finally {
      setIsCreatingAndRunning(false);
    }
  };

  return {
    session,
    messages,
    draftIssue,
    setDraftIssue,
    isStreaming,
    isStarting,
    isTerminating,
    isCreatingAndRunning,
    activeTool,
    error,
    startSession,
    sendMessage,
    terminateSession,
    createAndRun,
    resetSession: () => {
      closeStream();
      setSession(null);
      setMessages([]);
      setDraftIssue(null);
      setError(null);
    },
  };
}
