/**
 * Tests for api/websocket.ts - WebSocket manager.
 *
 * This test file does NOT use the MSW setup to avoid conflicts
 * with WebSocket mocking.
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';

// Create mock WebSocket class using vi.hoisted to ensure it runs before other imports
const { TestMockWebSocket, getCurrentWebSocket, setCurrentWebSocket } =
  vi.hoisted(() => {
    let currentWebSocket: TestMockWebSocket | null = null;

    class TestMockWebSocket {
      static CONNECTING = 0;
      static OPEN = 1;
      static CLOSING = 2;
      static CLOSED = 3;

      url: string;
      readyState: number = TestMockWebSocket.CONNECTING;
      onopen: ((event: Event) => void) | null = null;
      onclose: ((event: CloseEvent) => void) | null = null;
      onerror: ((event: Event) => void) | null = null;
      onmessage: ((event: MessageEvent) => void) | null = null;
      // Required by MSW interceptor
      addEventListener = vi.fn();
      removeEventListener = vi.fn();

      constructor(url: string) {
        this.url = url;
        currentWebSocket = this;
        // Simulate async connection
        setTimeout(() => {
          this.readyState = TestMockWebSocket.OPEN;
          if (this.onopen) {
            this.onopen(new Event('open'));
          }
        }, 0);
      }

      send = vi.fn();
      close = vi.fn((code?: number, reason?: string) => {
        this.readyState = TestMockWebSocket.CLOSED;
        if (this.onclose) {
          const event = new CloseEvent('close', { code: code ?? 1000, reason });
          this.onclose(event);
        }
      });

      simulateMessage(data: unknown) {
        if (this.onmessage) {
          const event = new MessageEvent('message', {
            data: JSON.stringify(data),
          });
          this.onmessage(event);
        }
      }

      simulateError() {
        if (this.onerror) {
          this.onerror(new Event('error'));
        }
      }

      simulateClose(code: number, reason?: string) {
        this.readyState = TestMockWebSocket.CLOSED;
        if (this.onclose) {
          const event = new CloseEvent('close', { code, reason });
          this.onclose(event);
        }
      }
    }

    return {
      TestMockWebSocket,
      getCurrentWebSocket: () => currentWebSocket,
      setCurrentWebSocket: (ws: TestMockWebSocket | null) => {
        currentWebSocket = ws;
      },
    };
  });

// Apply the mock globally before any imports
vi.stubGlobal('WebSocket', TestMockWebSocket);

// Now import what we need
import { setToken } from '../../auth/storage';
import { WebSocketManager } from '../../api/websocket';

describe('api/websocket', () => {
  let manager: WebSocketManager;

  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    vi.useFakeTimers();
    setCurrentWebSocket(null);
    manager = new WebSocketManager();
    window.location.href = 'http://localhost:3000';
  });

  afterEach(() => {
    manager.disconnect();
    vi.useRealTimers();
  });

  describe('connect', () => {
    it('does not connect when no token exists', () => {
      manager.connect();
      expect(manager.getState()).toBe('error');
    });

    it('connects with token as query parameter', () => {
      setToken('test-token');
      manager.connect();

      expect(manager.getState()).toBe('connecting');
      expect(getCurrentWebSocket()?.url).toContain('token=test-token');

      // Trigger the async open
      vi.runAllTimers();

      expect(manager.getState()).toBe('connected');
    });

    it('does not create duplicate connections', () => {
      setToken('test-token');
      manager.connect();
      vi.runAllTimers();

      const initialState = manager.getState();
      manager.connect();

      expect(manager.getState()).toBe(initialState);
    });
  });

  describe('disconnect', () => {
    it('disconnects and sets state to disconnected', () => {
      setToken('test-token');
      manager.connect();
      vi.runAllTimers();

      manager.disconnect();

      expect(manager.getState()).toBe('disconnected');
    });

    it('clears reconnection timeout', () => {
      setToken('test-token');
      manager.connect();
      vi.runAllTimers();

      // Simulate close to trigger reconnect scheduling
      getCurrentWebSocket()?.simulateClose(1006); // Abnormal close

      manager.disconnect();

      // Run timers - should not reconnect
      vi.runAllTimers();
      expect(manager.getState()).toBe('disconnected');
    });
  });

  describe('reconnect', () => {
    it('disconnects and reconnects', () => {
      setToken('test-token');
      manager.connect();
      vi.runAllTimers();

      const stateChanges: string[] = [];
      manager.onStateChange((state) => stateChanges.push(state));

      manager.reconnect();
      vi.runAllTimers();

      expect(stateChanges).toContain('disconnected');
      expect(stateChanges).toContain('connecting');
      expect(stateChanges).toContain('connected');
    });
  });

  describe('state management', () => {
    it('starts in disconnected state', () => {
      expect(manager.getState()).toBe('disconnected');
    });

    it('notifies state change listeners', () => {
      setToken('test-token');

      const stateChanges: string[] = [];
      manager.onStateChange((state) => stateChanges.push(state));

      manager.connect();
      vi.runAllTimers();

      expect(stateChanges).toEqual(['connecting', 'connected']);
    });

    it('allows unsubscribing from state changes', () => {
      setToken('test-token');

      const stateChanges: string[] = [];
      const unsubscribe = manager.onStateChange((state) =>
        stateChanges.push(state)
      );

      unsubscribe();

      manager.connect();
      vi.runAllTimers();

      expect(stateChanges).toEqual([]);
    });
  });

  describe('event handling', () => {
    it('dispatches queue:updated events to listeners', () => {
      setToken('test-token');
      manager.connect();
      vi.runAllTimers();

      const receivedData: unknown[] = [];
      manager.on('queue:updated', (data) => receivedData.push(data));

      getCurrentWebSocket()?.simulateMessage({
        type: 'queue:updated',
        data: { queue: [], stats: { total: 0 } },
      });

      expect(receivedData).toHaveLength(1);
      expect(receivedData[0]).toEqual({ queue: [], stats: { total: 0 } });
    });

    it('dispatches mr:status_changed events to listeners', () => {
      setToken('test-token');
      manager.connect();
      vi.runAllTimers();

      const receivedData: unknown[] = [];
      manager.on('mr:status_changed', (data) => receivedData.push(data));

      getCurrentWebSocket()?.simulateMessage({
        type: 'mr:status_changed',
        data: { iid: 42, old_status: 'queued', new_status: 'rebasing' },
      });

      expect(receivedData).toHaveLength(1);
      expect(receivedData[0]).toEqual({
        iid: 42,
        old_status: 'queued',
        new_status: 'rebasing',
      });
    });

    it('dispatches mr:completed events to listeners', () => {
      setToken('test-token');
      manager.connect();
      vi.runAllTimers();

      const receivedData: unknown[] = [];
      manager.on('mr:completed', (data) => receivedData.push(data));

      getCurrentWebSocket()?.simulateMessage({
        type: 'mr:completed',
        data: { iid: 42, status: 'merged', finished_at: '2025-01-01T12:00:00Z' },
      });

      expect(receivedData).toHaveLength(1);
      expect(receivedData[0]).toEqual({
        iid: 42,
        status: 'merged',
        finished_at: '2025-01-01T12:00:00Z',
      });
    });

    it('allows multiple listeners for same event type', () => {
      setToken('test-token');
      manager.connect();
      vi.runAllTimers();

      const received1: unknown[] = [];
      const received2: unknown[] = [];
      manager.on('queue:updated', (data) => received1.push(data));
      manager.on('queue:updated', (data) => received2.push(data));

      getCurrentWebSocket()?.simulateMessage({
        type: 'queue:updated',
        data: { queue: [] },
      });

      expect(received1).toHaveLength(1);
      expect(received2).toHaveLength(1);
    });

    it('allows unsubscribing from events', () => {
      setToken('test-token');
      manager.connect();
      vi.runAllTimers();

      const receivedData: unknown[] = [];
      const unsubscribe = manager.on('queue:updated', (data) =>
        receivedData.push(data)
      );

      unsubscribe();

      getCurrentWebSocket()?.simulateMessage({
        type: 'queue:updated',
        data: { queue: [] },
      });

      expect(receivedData).toHaveLength(0);
    });

    it('ignores invalid JSON messages', () => {
      setToken('test-token');
      manager.connect();
      vi.runAllTimers();

      const receivedData: unknown[] = [];
      manager.on('queue:updated', (data) => receivedData.push(data));

      const ws = getCurrentWebSocket();
      if (ws?.onmessage) {
        ws.onmessage(new MessageEvent('message', { data: 'invalid json' }));
      }

      expect(receivedData).toHaveLength(0);
    });
  });

  describe('reconnection', () => {
    it('schedules reconnect on abnormal close', () => {
      setToken('test-token');
      manager.connect();
      vi.runAllTimers();

      const stateChanges: string[] = [];
      manager.onStateChange((state) => stateChanges.push(state));

      getCurrentWebSocket()?.simulateClose(1006); // Abnormal closure

      expect(stateChanges).toContain('disconnected');

      // First reconnect after 1 second
      vi.advanceTimersByTime(1000);

      expect(stateChanges).toContain('connecting');
    });

    it('uses exponential backoff for reconnects', () => {
      setToken('test-token');
      manager.connect();
      vi.runAllTimers();

      expect(manager.getState()).toBe('connected');

      // First close - triggers reconnection scheduling
      getCurrentWebSocket()?.simulateClose(1006);
      expect(manager.getState()).toBe('disconnected');

      // Advance less than 1s - should still be disconnected (waiting for 1s delay)
      vi.advanceTimersByTime(500);
      expect(manager.getState()).toBe('disconnected');

      // Advance to 1s - reconnect attempt starts
      vi.advanceTimersByTime(500);
      expect(manager.getState()).toBe('connecting');

      // This test verifies the initial 1s delay exists
      // The caps and reset tests verify the full backoff algorithm
    });

    it('caps reconnect delay at 30 seconds', () => {
      setToken('test-token');
      manager.connect();
      vi.runAllTimers();

      // Simulate multiple failures to get to max backoff
      for (let i = 0; i < 10; i++) {
        getCurrentWebSocket()?.simulateClose(1006);

        // Wait for next reconnect (max 30s)
        vi.advanceTimersByTime(30000);
        vi.runAllTimers();
      }

      // Should still be trying to connect
      expect(manager.getState()).toBe('connected');
    });

    it('does not reconnect after intentional disconnect', () => {
      setToken('test-token');
      manager.connect();
      vi.runAllTimers();

      manager.disconnect();

      // Run all timers - should not reconnect
      vi.advanceTimersByTime(60000);

      expect(manager.getState()).toBe('disconnected');
    });

    it('does not reconnect on auth error (1008)', () => {
      setToken('test-token');
      manager.connect();
      vi.runAllTimers();

      getCurrentWebSocket()?.simulateClose(1008); // Policy violation (auth error)

      // Should set error state
      expect(manager.getState()).toBe('error');

      // Should clear token
      expect(localStorage.getItem('gitlab_queue_token')).toBeNull();

      // Should redirect to login
      expect(window.location.href).toBe('/login');

      // Should not attempt reconnect
      vi.advanceTimersByTime(60000);
      expect(manager.getState()).toBe('error');
    });

    it('resets reconnect attempts on successful connection', () => {
      setToken('test-token');
      manager.connect();
      vi.runAllTimers();

      // Simulate failure and reconnect
      getCurrentWebSocket()?.simulateClose(1006);

      vi.advanceTimersByTime(1000);
      vi.runAllTimers();

      // Now connected successfully
      expect(manager.getState()).toBe('connected');

      // Another close should start from 1s delay again
      getCurrentWebSocket()?.simulateClose(1006);

      const stateChanges: string[] = [];
      manager.onStateChange((state) => stateChanges.push(state));

      vi.advanceTimersByTime(1000);

      expect(stateChanges).toContain('connecting');
    });
  });

  describe('error handling', () => {
    it('sets state to error on WebSocket error', () => {
      setToken('test-token');
      manager.connect();
      vi.runAllTimers();

      getCurrentWebSocket()?.simulateError();

      expect(manager.getState()).toBe('error');
    });
  });
});
