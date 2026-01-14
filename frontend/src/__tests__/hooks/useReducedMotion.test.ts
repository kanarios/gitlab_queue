/**
 * Tests for hooks/useReducedMotion.ts - Reduced motion preference hook.
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useReducedMotion } from '../../hooks/useReducedMotion';

describe('hooks/useReducedMotion', () => {
  let mediaQueryListeners: Map<string, (e: MediaQueryListEvent) => void>;
  let mockMatchMedia: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    mediaQueryListeners = new Map();

    mockMatchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: (
        _: string,
        handler: (e: MediaQueryListEvent) => void
      ) => {
        mediaQueryListeners.set(query, handler);
      },
      removeEventListener: (_: string) => {
        mediaQueryListeners.delete(query);
      },
      dispatchEvent: vi.fn(),
    }));

    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: mockMatchMedia,
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('initial state', () => {
    it('returns false when user prefers motion', () => {
      const { result } = renderHook(() => useReducedMotion());
      expect(result.current).toBe(false);
    });

    it('returns true when user prefers reduced motion', () => {
      mockMatchMedia.mockImplementation((query: string) => ({
        matches: query === '(prefers-reduced-motion: reduce)',
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }));

      const { result } = renderHook(() => useReducedMotion());
      expect(result.current).toBe(true);
    });
  });

  describe('preference changes', () => {
    it('updates when preference changes from no-preference to reduce', () => {
      const { result } = renderHook(() => useReducedMotion());

      expect(result.current).toBe(false);

      // Simulate preference change
      const handler = mediaQueryListeners.get(
        '(prefers-reduced-motion: reduce)'
      );
      if (handler) {
        act(() => {
          handler({ matches: true } as MediaQueryListEvent);
        });
      }

      expect(result.current).toBe(true);
    });

    it('updates when preference changes from reduce to no-preference', () => {
      mockMatchMedia.mockImplementation((query: string) => ({
        matches: query === '(prefers-reduced-motion: reduce)',
        media: query,
        addEventListener: (
          _: string,
          handler: (e: MediaQueryListEvent) => void
        ) => {
          mediaQueryListeners.set(query, handler);
        },
        removeEventListener: vi.fn(),
      }));

      const { result } = renderHook(() => useReducedMotion());

      expect(result.current).toBe(true);

      // Simulate preference change
      const handler = mediaQueryListeners.get(
        '(prefers-reduced-motion: reduce)'
      );
      if (handler) {
        act(() => {
          handler({ matches: false } as MediaQueryListEvent);
        });
      }

      expect(result.current).toBe(false);
    });
  });

  describe('cleanup', () => {
    it('removes event listener on unmount', () => {
      const removeEventListenerMock = vi.fn();
      mockMatchMedia.mockImplementation((query: string) => ({
        matches: false,
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: removeEventListenerMock,
      }));

      const { unmount } = renderHook(() => useReducedMotion());

      unmount();

      expect(removeEventListenerMock).toHaveBeenCalledWith(
        'change',
        expect.any(Function)
      );
    });
  });
});
