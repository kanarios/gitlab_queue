/**
 * React hook for WebSocket connection and queue state management.
 *
 * Provides:
 * - Automatic connection on mount (if authenticated)
 * - Real-time queue updates
 * - Connection state for UI feedback
 * - Cleanup on unmount
 */

import { useState, useEffect, useCallback } from 'react';
import { wsManager } from '../api/websocket';
import { hasToken } from '../auth/storage';
import type { MergeRequest, QueueStatsFromWS, WebSocketState } from '../types';

interface UseWebSocketResult {
  /** Current connection state. */
  state: WebSocketState;
  /** Current queue items (MRs being processed). */
  queue: MergeRequest[];
  /** Queue statistics by state. */
  stats: QueueStatsFromWS | null;
  /** Manually trigger reconnection. */
  reconnect: () => void;
}

/**
 * Hook for managing WebSocket connection and queue state.
 *
 * @example
 * ```tsx
 * function Dashboard() {
 *   const { state, queue, stats, reconnect } = useWebSocket();
 *
 *   if (state === 'connecting') return <Loading />;
 *   if (state === 'error') return <Error onRetry={reconnect} />;
 *
 *   return <QueueList items={queue} stats={stats} />;
 * }
 * ```
 */
export function useWebSocket(projectId: number | null): UseWebSocketResult {
  const [state, setState] = useState<WebSocketState>(
    projectId === null || !hasToken() ? 'disconnected' : 'connecting'
  );
  const [queue, setQueue] = useState<MergeRequest[]>([]);
  const [stats, setStats] = useState<QueueStatsFromWS | null>(null);

  // Handle queue:updated event - full queue replacement
  const handleQueueUpdated = useCallback(
    (data: { project_id: number; queue: MergeRequest[]; stats: QueueStatsFromWS }) => {
      if (data.project_id === projectId) {
        setQueue(data.queue);
        setStats(data.stats);
      }
    },
    [projectId]
  );

  // Handle mr:status_changed event - update single MR status
  const handleStatusChanged = useCallback(
    (data: { project_id: number; iid: number; oldStatus: string; newStatus: string }) => {
      if (data.project_id === projectId) {
        setQueue((prev) =>
          prev.map((mr) =>
            mr.mr_iid === data.iid
              ? { ...mr, status: data.newStatus as MergeRequest['status'] }
              : mr
          )
        );
      }
    },
    [projectId]
  );

  // Handle mr:completed event - remove MR from queue
  const handleCompleted = useCallback(
    (data: { project_id: number; iid: number; status: string; finishedAt: string; failureReason: string | null }) => {
      if (data.project_id === projectId) {
        setQueue((prev) => prev.filter((mr) => mr.mr_iid !== data.iid));
      }
    },
    [projectId]
  );

  // Reconnect handler for UI
  const reconnect = useCallback(() => {
    if (projectId !== null) wsManager.reconnect(projectId);
  }, [projectId]);

  useEffect(() => {
    setQueue([]);
    setStats(null);
    setState(projectId === null || !hasToken() ? 'disconnected' : 'connecting');

    if (projectId === null) {
      return;
    }

    // Subscribe to state changes
    const unsubState = wsManager.onStateChange((newState) => {
      setState(newState);
    });

    // Subscribe to events
    const unsubQueueUpdated = wsManager.on('queue:updated', handleQueueUpdated);
    const unsubStatusChanged = wsManager.on('mr:status_changed', handleStatusChanged);
    const unsubCompleted = wsManager.on('mr:completed', handleCompleted);

    // Connect if authenticated
    if (hasToken()) wsManager.connect(projectId);

    return () => {
      unsubState();
      unsubQueueUpdated();
      unsubStatusChanged();
      unsubCompleted();
      wsManager.disconnect();
    };
  }, [projectId, handleQueueUpdated, handleStatusChanged, handleCompleted]);

  return {
    state,
    queue,
    stats,
    reconnect,
  };
}
