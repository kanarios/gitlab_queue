/**
 * Tests for hooks/useWebSocket.ts - WebSocket hook.
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useWebSocket } from '../../hooks/useWebSocket';
import { wsManager, WebSocketManager } from '../../api/websocket';
import { setToken, clearToken } from '../../auth/storage';
import type { MergeRequest, QueueStatsFromWS } from '../../types';

// Mock the wsManager module
vi.mock('../../api/websocket', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/websocket')>();
  return {
    ...actual,
    wsManager: {
      getState: vi.fn(() => 'disconnected'),
      connect: vi.fn(),
      disconnect: vi.fn(),
      reconnect: vi.fn(),
      onStateChange: vi.fn(() => vi.fn()),
      on: vi.fn(() => vi.fn()),
    },
  };
});

describe('hooks/useWebSocket', () => {
  const mockWsManager = wsManager as unknown as {
    getState: ReturnType<typeof vi.fn>;
    connect: ReturnType<typeof vi.fn>;
    disconnect: ReturnType<typeof vi.fn>;
    reconnect: ReturnType<typeof vi.fn>;
    onStateChange: ReturnType<typeof vi.fn>;
    on: ReturnType<typeof vi.fn>;
  };

  let stateChangeCallback: ((state: string) => void) | null = null;
  let eventCallbacks: Map<string, (data: unknown) => void> = new Map();

  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();

    stateChangeCallback = null;
    eventCallbacks = new Map();

    mockWsManager.getState.mockReturnValue('disconnected');
    mockWsManager.onStateChange.mockImplementation(
      (callback: (state: string) => void) => {
        stateChangeCallback = callback;
        return vi.fn();
      }
    );
    mockWsManager.on.mockImplementation(
      (eventType: string, callback: (data: unknown) => void) => {
        eventCallbacks.set(eventType, callback);
        return vi.fn();
      }
    );
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('initial state', () => {
    it('returns initial disconnected state', () => {
      const { result } = renderHook(() => useWebSocket());

      expect(result.current.state).toBe('disconnected');
      expect(result.current.queue).toEqual([]);
      expect(result.current.stats).toBeNull();
    });

    it('connects when token exists', () => {
      setToken('test-token');

      renderHook(() => useWebSocket());

      expect(mockWsManager.connect).toHaveBeenCalled();
    });

    it('does not connect when no token', () => {
      renderHook(() => useWebSocket());

      expect(mockWsManager.connect).not.toHaveBeenCalled();
    });
  });

  describe('state updates', () => {
    it('updates state when connection state changes', () => {
      const { result } = renderHook(() => useWebSocket());

      act(() => {
        stateChangeCallback?.('connecting');
      });

      expect(result.current.state).toBe('connecting');

      act(() => {
        stateChangeCallback?.('connected');
      });

      expect(result.current.state).toBe('connected');
    });
  });

  describe('queue:updated event', () => {
    it('updates queue and stats on queue:updated event', () => {
      const { result } = renderHook(() => useWebSocket());

      const mockQueue: MergeRequest[] = [
        {
          mr_iid: 42,
          title: 'Test MR',
          author: { name: 'Test', username: 'test', avatar_url: null },
          status: 'queued',
          labels: [],
          is_hotfix: false,
          queued_at: '2025-01-01T10:00:00Z',
          started_at: null,
          finished_at: null,
          target_branch: 'main',
          pipeline: null,
          failure_reason: null,
        },
      ];

      const mockStats: QueueStatsFromWS = {
        queued: 1,
        rebasing: 0,
        testing: 0,
        merging: 0,
      };

      const callback = eventCallbacks.get('queue:updated');
      act(() => {
        callback?.({ queue: mockQueue, stats: mockStats });
      });

      expect(result.current.queue).toEqual(mockQueue);
      expect(result.current.stats).toEqual(mockStats);
    });
  });

  describe('mr:status_changed event', () => {
    it('updates MR status on mr:status_changed event', () => {
      const { result } = renderHook(() => useWebSocket());

      // First, set up queue with an MR
      const mockQueue: MergeRequest[] = [
        {
          mr_iid: 42,
          title: 'Test MR',
          author: { name: 'Test', username: 'test', avatar_url: null },
          status: 'queued',
          labels: [],
          is_hotfix: false,
          queued_at: '2025-01-01T10:00:00Z',
          started_at: null,
          finished_at: null,
          target_branch: 'main',
          pipeline: null,
          failure_reason: null,
        },
      ];

      const queueCallback = eventCallbacks.get('queue:updated');
      act(() => {
        queueCallback?.({ queue: mockQueue, stats: null });
      });

      expect(result.current.queue[0].status).toBe('queued');

      // Now update the status
      const statusCallback = eventCallbacks.get('mr:status_changed');
      act(() => {
        statusCallback?.({ iid: 42, oldStatus: 'queued', newStatus: 'rebasing' });
      });

      expect(result.current.queue[0].status).toBe('rebasing');
    });

    it('does not update non-matching MR', () => {
      const { result } = renderHook(() => useWebSocket());

      const mockQueue: MergeRequest[] = [
        {
          mr_iid: 42,
          title: 'Test MR',
          author: { name: 'Test', username: 'test', avatar_url: null },
          status: 'queued',
          labels: [],
          is_hotfix: false,
          queued_at: '2025-01-01T10:00:00Z',
          started_at: null,
          finished_at: null,
          target_branch: 'main',
          pipeline: null,
          failure_reason: null,
        },
      ];

      const queueCallback = eventCallbacks.get('queue:updated');
      act(() => {
        queueCallback?.({ queue: mockQueue, stats: null });
      });

      // Try to update different MR
      const statusCallback = eventCallbacks.get('mr:status_changed');
      act(() => {
        statusCallback?.({ iid: 99, oldStatus: 'queued', newStatus: 'rebasing' });
      });

      // Original MR should be unchanged
      expect(result.current.queue[0].status).toBe('queued');
    });
  });

  describe('mr:completed event', () => {
    it('removes MR from queue on mr:completed event', () => {
      const { result } = renderHook(() => useWebSocket());

      const mockQueue: MergeRequest[] = [
        {
          mr_iid: 42,
          title: 'Test MR 1',
          author: { name: 'Test', username: 'test', avatar_url: null },
          status: 'merging',
          labels: [],
          is_hotfix: false,
          queued_at: '2025-01-01T10:00:00Z',
          started_at: null,
          finished_at: null,
          target_branch: 'main',
          pipeline: null,
          failure_reason: null,
        },
        {
          mr_iid: 43,
          title: 'Test MR 2',
          author: { name: 'Test', username: 'test', avatar_url: null },
          status: 'queued',
          labels: [],
          is_hotfix: false,
          queued_at: '2025-01-01T10:01:00Z',
          started_at: null,
          finished_at: null,
          target_branch: 'main',
          pipeline: null,
          failure_reason: null,
        },
      ];

      const queueCallback = eventCallbacks.get('queue:updated');
      act(() => {
        queueCallback?.({ queue: mockQueue, stats: null });
      });

      expect(result.current.queue).toHaveLength(2);

      // Complete MR 42
      const completedCallback = eventCallbacks.get('mr:completed');
      act(() => {
        completedCallback?.({
          iid: 42,
          status: 'merged',
          finishedAt: '2025-01-01T12:00:00Z',
          failureReason: null,
        });
      });

      expect(result.current.queue).toHaveLength(1);
      expect(result.current.queue[0].mr_iid).toBe(43);
    });
  });

  describe('reconnect', () => {
    it('provides reconnect function', () => {
      const { result } = renderHook(() => useWebSocket());

      act(() => {
        result.current.reconnect();
      });

      expect(mockWsManager.reconnect).toHaveBeenCalled();
    });
  });

  describe('cleanup', () => {
    it('unsubscribes from all events on unmount', () => {
      const unsubState = vi.fn();
      const unsubQueue = vi.fn();
      const unsubStatus = vi.fn();
      const unsubCompleted = vi.fn();

      mockWsManager.onStateChange.mockReturnValue(unsubState);
      mockWsManager.on.mockImplementation((eventType: string) => {
        if (eventType === 'queue:updated') return unsubQueue;
        if (eventType === 'mr:status_changed') return unsubStatus;
        if (eventType === 'mr:completed') return unsubCompleted;
        return vi.fn();
      });

      const { unmount } = renderHook(() => useWebSocket());

      unmount();

      expect(unsubState).toHaveBeenCalled();
      expect(unsubQueue).toHaveBeenCalled();
      expect(unsubStatus).toHaveBeenCalled();
      expect(unsubCompleted).toHaveBeenCalled();
    });
  });
});
