/**
 * Vitest test setup file.
 *
 * Configures:
 * - Jest DOM matchers
 * - MSW server for API mocking
 * - Global mocks (localStorage, WebSocket, window.location)
 */

import '@testing-library/jest-dom/vitest';
import { afterAll, afterEach, beforeAll, beforeEach, vi } from 'vitest';
import { server } from './mocks/server';

// Start MSW server before all tests
beforeAll(() => {
  // Use 'warn' instead of 'error' to allow WebSocket requests through
  server.listen({ onUnhandledRequest: 'warn' });
});

// Reset handlers and mocks before each test
beforeEach(() => {
  // Reset localStorage store
  localStorageStore = {};
  // Reset window.location
  window.location.href = 'http://localhost:3000';
});

// Reset handlers after each test
afterEach(() => {
  server.resetHandlers();
  vi.restoreAllMocks();
});

// Stop MSW server after all tests
afterAll(() => {
  server.close();
});

// Mock window.location
const mockLocation = {
  href: 'http://localhost:3000',
  origin: 'http://localhost:3000',
  protocol: 'http:',
  host: 'localhost:3000',
  hostname: 'localhost',
  port: '3000',
  pathname: '/',
  search: '',
  hash: '',
  assign: vi.fn(),
  replace: vi.fn(),
  reload: vi.fn(),
};

Object.defineProperty(window, 'location', {
  value: mockLocation,
  writable: true,
});

// Mock localStorage with shared store that can be reset
let localStorageStore: Record<string, string> = {};

const localStorageMock = {
  getItem: (key: string) => localStorageStore[key] ?? null,
  setItem: (key: string, value: string) => {
    localStorageStore[key] = value;
  },
  removeItem: (key: string) => {
    delete localStorageStore[key];
  },
  clear: () => {
    localStorageStore = {};
  },
  get length() {
    return Object.keys(localStorageStore).length;
  },
  key: (index: number) => Object.keys(localStorageStore)[index] ?? null,
};

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
  writable: true,
});

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  url: string;
  readyState: number = MockWebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    // Simulate async connection
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
    }, 0);
  }

  send = vi.fn();

  close(code?: number, reason?: string) {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      const event = new CloseEvent('close', { code: code ?? 1000, reason });
      this.onclose(event);
    }
  }

  // Test helper to simulate receiving a message
  simulateMessage(data: unknown) {
    if (this.onmessage) {
      const event = new MessageEvent('message', {
        data: JSON.stringify(data),
      });
      this.onmessage(event);
    }
  }

  // Test helper to simulate an error
  simulateError() {
    if (this.onerror) {
      this.onerror(new Event('error'));
    }
  }

  // Test helper to simulate close with specific code
  simulateClose(code: number, reason?: string) {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      const event = new CloseEvent('close', { code, reason });
      this.onclose(event);
    }
  }
}

// Assign static properties
Object.assign(MockWebSocket, {
  CONNECTING: 0,
  OPEN: 1,
  CLOSING: 2,
  CLOSED: 3,
});

vi.stubGlobal('WebSocket', MockWebSocket);

// Export for use in tests
export { MockWebSocket };
