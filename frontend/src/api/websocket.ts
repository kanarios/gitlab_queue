/**
 * WebSocket client for real-time queue updates.
 *
 * Features:
 * - Exponential backoff reconnection (1s, 2s, 4s, 8s, max 30s)
 * - No reconnect on auth errors (code 1008)
 * - Type-safe event handling
 * - Connection state management
 */

import { getToken, clearToken } from '../auth/storage';
import type { WSEvent, WebSocketState } from '../types';

/** WebSocket close code for policy violation (auth errors). */
const CLOSE_CODE_POLICY_VIOLATION = 1008;

/** Initial reconnect delay in milliseconds. */
const INITIAL_RECONNECT_DELAY = 1000;

/** Maximum reconnect delay in milliseconds. */
const MAX_RECONNECT_DELAY = 30000;

type EventCallback<T> = (data: T) => void;
type StateChangeCallback = (state: WebSocketState) => void;

/**
 * WebSocket manager for connecting to the queue updates endpoint.
 *
 * @example
 * ```typescript
 * const manager = new WebSocketManager();
 * manager.onStateChange((state) => console.log('State:', state));
 * manager.on('queue:updated', (data) => console.log('Queue:', data.queue));
 * manager.connect();
 * ```
 */
export class WebSocketManager {
  private socket: WebSocket | null = null;
  private state: WebSocketState = 'disconnected';
  private reconnectAttempts = 0;
  private reconnectTimeoutId: ReturnType<typeof setTimeout> | null = null;
  private stateListeners = new Set<StateChangeCallback>();
  private eventListeners = new Map<string, Set<EventCallback<unknown>>>();
  private intentionalDisconnect = false;

  /**
   * Get the WebSocket endpoint URL.
   * Uses Vite's proxy in development.
   */
  private getWsUrl(): string {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${wsProtocol}//${window.location.host}/ws/queue`;
  }

  /**
   * Get current connection state.
   */
  getState(): WebSocketState {
    return this.state;
  }

  /**
   * Update connection state and notify listeners.
   */
  private setState(newState: WebSocketState): void {
    if (this.state !== newState) {
      this.state = newState;
      this.stateListeners.forEach((callback) => callback(newState));
    }
  }

  /**
   * Subscribe to connection state changes.
   * @returns Unsubscribe function.
   */
  onStateChange(callback: StateChangeCallback): () => void {
    this.stateListeners.add(callback);
    return () => this.stateListeners.delete(callback);
  }

  /**
   * Subscribe to WebSocket events.
   * @param type - Event type ('queue:updated', 'mr:status_changed', 'mr:completed')
   * @param callback - Handler function
   * @returns Unsubscribe function.
   */
  on<T extends WSEvent['type']>(
    type: T,
    callback: EventCallback<Extract<WSEvent, { type: T }>['data']>
  ): () => void {
    if (!this.eventListeners.has(type)) {
      this.eventListeners.set(type, new Set());
    }
    this.eventListeners.get(type)!.add(callback as EventCallback<unknown>);

    return () => {
      const listeners = this.eventListeners.get(type);
      if (listeners) {
        listeners.delete(callback as EventCallback<unknown>);
      }
    };
  }

  /**
   * Dispatch event to registered listeners.
   */
  private dispatchEvent(event: WSEvent): void {
    const listeners = this.eventListeners.get(event.type);
    if (listeners) {
      listeners.forEach((callback) => callback(event.data));
    }
  }

  /**
   * Connect to the WebSocket endpoint.
   * Requires authentication token to be present.
   */
  connect(): void {
    if (
      this.socket?.readyState === WebSocket.OPEN ||
      this.socket?.readyState === WebSocket.CONNECTING
    ) {
      return;
    }

    const token = getToken();
    if (!token) {
      this.setState('error');
      return;
    }

    this.intentionalDisconnect = false;
    this.setState('connecting');

    const url = `${this.getWsUrl()}?token=${encodeURIComponent(token)}`;
    this.socket = new WebSocket(url);

    this.socket.onopen = this.handleOpen.bind(this);
    this.socket.onclose = this.handleClose.bind(this);
    this.socket.onerror = this.handleError.bind(this);
    this.socket.onmessage = this.handleMessage.bind(this);
  }

  /**
   * Disconnect from the WebSocket endpoint.
   * Does not trigger reconnection.
   */
  disconnect(): void {
    this.intentionalDisconnect = true;
    this.clearReconnectTimeout();

    if (this.socket) {
      this.socket.onopen = null;
      this.socket.onclose = null;
      this.socket.onerror = null;
      this.socket.onmessage = null;
      this.socket.close();
      this.socket = null;
    }

    this.setState('disconnected');
  }

  /**
   * Force reconnection attempt.
   */
  reconnect(): void {
    this.disconnect();
    this.intentionalDisconnect = false;
    this.reconnectAttempts = 0;
    this.connect();
  }

  /**
   * Handle WebSocket open event.
   */
  private handleOpen(): void {
    this.reconnectAttempts = 0;
    this.setState('connected');
  }

  /**
   * Handle WebSocket close event.
   */
  private handleClose(event: CloseEvent): void {
    this.socket = null;

    // Auth error - don't reconnect, clear token, redirect to login
    if (event.code === CLOSE_CODE_POLICY_VIOLATION) {
      clearToken();
      this.setState('error');
      window.location.href = '/login';
      return;
    }

    this.setState('disconnected');

    // Don't reconnect if intentionally disconnected
    if (this.intentionalDisconnect) {
      return;
    }

    // Schedule reconnection with exponential backoff
    this.scheduleReconnect();
  }

  /**
   * Handle WebSocket error event.
   */
  private handleError(): void {
    this.setState('error');
  }

  /**
   * Handle WebSocket message event.
   */
  private handleMessage(event: MessageEvent): void {
    try {
      const data = JSON.parse(event.data) as WSEvent;
      this.dispatchEvent(data);
    } catch {
      // Invalid JSON - ignore
    }
  }

  /**
   * Schedule reconnection with exponential backoff.
   */
  private scheduleReconnect(): void {
    this.clearReconnectTimeout();

    const delay = Math.min(
      INITIAL_RECONNECT_DELAY * Math.pow(2, this.reconnectAttempts),
      MAX_RECONNECT_DELAY
    );

    this.reconnectAttempts++;

    this.reconnectTimeoutId = setTimeout(() => {
      this.connect();
    }, delay);
  }

  /**
   * Clear pending reconnection timeout.
   */
  private clearReconnectTimeout(): void {
    if (this.reconnectTimeoutId !== null) {
      clearTimeout(this.reconnectTimeoutId);
      this.reconnectTimeoutId = null;
    }
  }
}

/** Singleton WebSocket manager instance. */
export const wsManager = new WebSocketManager();
