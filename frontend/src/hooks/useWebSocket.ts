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
  /** Whether this project has received a full queue snapshot. */
  hasSnapshot: boolean;
  /** Whether the current connection has received a full queue snapshot. */
  isSynchronized: boolean;
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
  const [hasSnapshot, setHasSnapshot] = useState(false);
  const [isSynchronized, setIsSynchronized] = useState(false);

  // Handle queue:updated event - full queue replacement
  const handleQueueUpdated = useCallback(
    (data: { project_id: number; queue: MergeRequest[]; stats: QueueStatsFromWS }) => {
      if (data.project_id === projectId) {
        setQueue(data.queue);
        setStats(data.stats);
        setHasSnapshot(true);
        setIsSynchronized(true);
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
    (data: {
      project_id: number;
      iid: number;
      status: string;
      finishedAt: string;
      failureReason: string | null;
    }) => {
      if (data.project_id === projectId) {
        setQueue((prev) => prev.filter((mr) => mr.mr_iid !== data.iid));
      }
    },
    [projectId]
  );

  // Reconnect handler for UI
  const reconnect = useCallback(() => {
    if (projectId !== null) {
      setIsSynchronized(false);
      wsManager.reconnect(projectId);
    }
  }, [projectId]);

  useEffect(() => {
    setQueue([]);
    setStats(null);
    setHasSnapshot(false);
    setIsSynchronized(false);
    setState(projectId === null || !hasToken() ? 'disconnected' : 'connecting');

    if (projectId === null) {
      return;
    }

    // Ignore callbacks already queued by a subscription that has been disposed.
    let active = true;
    // Subscribe to state changes
    const unsubState = wsManager.onStateChange((newState) => {
      if (!active) return;
      setState(newState);
      if (newState !== 'connected') setIsSynchronized(false);
    });

    // Subscribe to events
    const unsubQueueUpdated = wsManager.on('queue:updated', (data) => {
      if (active) handleQueueUpdated(data);
    });
    const unsubStatusChanged = wsManager.on('mr:status_changed', (data) => {
      if (active) handleStatusChanged(data);
    });
    const unsubCompleted = wsManager.on('mr:completed', (data) => {
      if (active) handleCompleted(data);
    });

    // Connect if authenticated
    if (hasToken()) wsManager.connect(projectId);

    return () => {
      active = false;
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
    hasSnapshot,
    isSynchronized,
    reconnect,
  };
}
