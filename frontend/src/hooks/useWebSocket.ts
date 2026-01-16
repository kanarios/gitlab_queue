/**
 * React hook for WebSocket connection and queue state management.
 *
 * Provides:
 * - Automatic connection on mount (if authenticated)
 * - Real-time queue updates
 * - Connection state for UI feedback
 * - Cleanup on unmount
 */

import { useState, useEffect, useCallback, useRef } from 'react';
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
export function useWebSocket(): UseWebSocketResult {
  const [state, setState] = useState<WebSocketState>(wsManager.getState());
  const [queue, setQueue] = useState<MergeRequest[]>([]);
  const [stats, setStats] = useState<QueueStatsFromWS | null>(null);

  // Track if component is mounted to prevent state updates after unmount
  const isMounted = useRef(true);

  // Handle queue:updated event - full queue replacement
  const handleQueueUpdated = useCallback(
    (data: { queue: MergeRequest[]; stats: QueueStatsFromWS }) => {
      if (isMounted.current) {
        setQueue(data.queue);
        setStats(data.stats);
      }
    },
    []
  );

  // Handle mr:status_changed event - update single MR status
  const handleStatusChanged = useCallback(
    (data: { iid: number; oldStatus: string; newStatus: string }) => {
      if (isMounted.current) {
        setQueue((prev) =>
          prev.map((mr) =>
            mr.mr_iid === data.iid
              ? { ...mr, status: data.newStatus as MergeRequest['status'] }
              : mr
          )
        );
      }
    },
    []
  );

  // Handle mr:completed event - remove MR from queue
  const handleCompleted = useCallback(
    (data: { iid: number; status: string; finishedAt: string; failureReason: string | null }) => {
      if (isMounted.current) {
        setQueue((prev) => prev.filter((mr) => mr.mr_iid !== data.iid));
      }
    },
    []
  );

  // Reconnect handler for UI
  const reconnect = useCallback(() => {
    wsManager.reconnect();
  }, []);

  useEffect(() => {
    isMounted.current = true;

    // Subscribe to state changes
    const unsubState = wsManager.onStateChange((newState) => {
      if (isMounted.current) {
        setState(newState);
      }
    });

    // Subscribe to events
    const unsubQueueUpdated = wsManager.on('queue:updated', handleQueueUpdated);
    const unsubStatusChanged = wsManager.on('mr:status_changed', handleStatusChanged);
    const unsubCompleted = wsManager.on('mr:completed', handleCompleted);

    // Connect if authenticated
    if (hasToken()) {
      wsManager.connect();
    }

    return () => {
      isMounted.current = false;
      unsubState();
      unsubQueueUpdated();
      unsubStatusChanged();
      unsubCompleted();
      // Note: Don't disconnect here - other components may still be using the connection
      // The manager is a singleton and handles its own lifecycle
    };
  }, [handleQueueUpdated, handleStatusChanged, handleCompleted]);

  return {
    state,
    queue,
    stats,
    reconnect,
  };
}
