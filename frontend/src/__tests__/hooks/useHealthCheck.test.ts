/**
 * Tests for hooks/useHealthCheck.ts - Health check hook.
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import { useHealthCheck } from '../../hooks/useHealthCheck';

const mockHealthResponse = {
  ready: true,
  status: 'ready' as const,
  mode: 'normal' as const,
  components: {
    database: { status: 'healthy' as const, connected: true },
    gitlab: { status: 'healthy' as const },
  },
};

describe('hooks/useHealthCheck', () => {
  beforeEach(() => {
    server.use(
      http.get('/ready', () => {
        return HttpResponse.json(mockHealthResponse);
      })
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initial state', () => {
    it('starts with loading state', () => {
      const { result } = renderHook(() => useHealthCheck());

      expect(result.current.isLoading).toBe(true);
      expect(result.current.health).toBeNull();
    });
  });

  describe('successful health check', () => {
    it('loads health status on mount', async () => {
      const { result } = renderHook(() => useHealthCheck());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.health?.ready).toBe(true);
      expect(result.current.isHealthy).toBe(true);
      expect(result.current.mode).toBe('normal');
      expect(result.current.error).toBeNull();
    });
  });

  describe('failed health check', () => {
    it('sets error on failure', async () => {
      server.use(
        http.get('/ready', () => {
          return HttpResponse.error();
        })
      );

      const { result } = renderHook(() => useHealthCheck());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).not.toBeNull();
      expect(result.current.isHealthy).toBe(false);
      expect(result.current.mode).toBe('unknown');
    });
  });

  describe('refetch', () => {
    it('allows manual refetch', async () => {
      const { result } = renderHook(() => useHealthCheck());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Change the mock to return unhealthy
      server.use(
        http.get('/ready', () => {
          return HttpResponse.json({
            ...mockHealthResponse,
            ready: false,
            mode: 'degraded',
          });
        })
      );

      // Trigger refetch
      await act(async () => {
        await result.current.refetch();
      });

      expect(result.current.health?.ready).toBe(false);
      expect(result.current.mode).toBe('degraded');
    });
  });
});
