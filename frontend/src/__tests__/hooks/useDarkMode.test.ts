/**
 * Tests for hooks/useDarkMode.ts - Dark mode hook.
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDarkMode } from '../../hooks/useDarkMode';

describe('hooks/useDarkMode', () => {
  let mediaQueryListeners: Map<string, (e: MediaQueryListEvent) => void>;
  let mockMatchMedia: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove('dark');
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
    it('defaults to system theme when nothing stored', () => {
      const { result } = renderHook(() => useDarkMode());
      expect(result.current.theme).toBe('system');
    });

    it('loads stored theme from localStorage', () => {
      localStorage.setItem('theme', 'dark');
      const { result } = renderHook(() => useDarkMode());
      expect(result.current.theme).toBe('dark');
    });

    it('ignores invalid stored values', () => {
      localStorage.setItem('theme', 'invalid');
      const { result } = renderHook(() => useDarkMode());
      expect(result.current.theme).toBe('system');
    });
  });

  describe('isDark calculation', () => {
    it('returns false when theme is light', () => {
      localStorage.setItem('theme', 'light');
      const { result } = renderHook(() => useDarkMode());
      expect(result.current.isDark).toBe(false);
    });

    it('returns true when theme is dark', () => {
      localStorage.setItem('theme', 'dark');
      const { result } = renderHook(() => useDarkMode());
      expect(result.current.isDark).toBe(true);
    });

    it('follows system preference when theme is system', () => {
      // System preference is dark
      mockMatchMedia.mockImplementation((query: string) => ({
        matches: query === '(prefers-color-scheme: dark)',
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }));

      const { result } = renderHook(() => useDarkMode());
      expect(result.current.isDark).toBe(true);
    });
  });

  describe('DOM manipulation', () => {
    it('adds dark class when isDark is true', () => {
      localStorage.setItem('theme', 'dark');
      renderHook(() => useDarkMode());
      expect(document.documentElement.classList.contains('dark')).toBe(true);
    });

    it('removes dark class when isDark is false', () => {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'light');
      renderHook(() => useDarkMode());
      expect(document.documentElement.classList.contains('dark')).toBe(false);
    });
  });

  describe('setTheme', () => {
    it('updates theme state', () => {
      const { result } = renderHook(() => useDarkMode());

      act(() => {
        result.current.setTheme('dark');
      });

      expect(result.current.theme).toBe('dark');
    });

    it('persists theme to localStorage', () => {
      const { result } = renderHook(() => useDarkMode());

      act(() => {
        result.current.setTheme('light');
      });

      expect(localStorage.getItem('theme')).toBe('light');
    });
  });

  describe('toggleTheme', () => {
    it('toggles from light to dark', () => {
      localStorage.setItem('theme', 'light');
      const { result } = renderHook(() => useDarkMode());

      act(() => {
        result.current.toggleTheme();
      });

      expect(result.current.theme).toBe('dark');
      expect(result.current.isDark).toBe(true);
    });

    it('toggles from dark to light', () => {
      localStorage.setItem('theme', 'dark');
      const { result } = renderHook(() => useDarkMode());

      act(() => {
        result.current.toggleTheme();
      });

      expect(result.current.theme).toBe('light');
      expect(result.current.isDark).toBe(false);
    });

    it('toggles from system (dark) to light', () => {
      mockMatchMedia.mockImplementation((query: string) => ({
        matches: query === '(prefers-color-scheme: dark)',
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }));

      const { result } = renderHook(() => useDarkMode());
      expect(result.current.isDark).toBe(true);

      act(() => {
        result.current.toggleTheme();
      });

      expect(result.current.theme).toBe('light');
      expect(result.current.isDark).toBe(false);
    });
  });

  describe('system preference changes', () => {
    it('updates when system preference changes', () => {
      const { result } = renderHook(() => useDarkMode());

      expect(result.current.isDark).toBe(false); // Default system preference is light

      // Simulate system preference change to dark
      const handler = mediaQueryListeners.get('(prefers-color-scheme: dark)');
      if (handler) {
        act(() => {
          handler({ matches: true } as MediaQueryListEvent);
        });
      }

      expect(result.current.isDark).toBe(true);
    });
  });
});
