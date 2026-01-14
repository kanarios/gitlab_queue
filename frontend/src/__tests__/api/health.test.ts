/**
 * Tests for api/health.ts - Health check API.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import { getReadyStatus } from '../../api/health';

const mockHealthResponse = {
  ready: true,
  status: 'ready' as const,
  mode: 'normal' as const,
  components: {
    database: { status: 'healthy' as const, connected: true },
    gitlab: { status: 'healthy' as const },
  },
};

describe('api/health', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    server.use(
      http.get('/ready', () => {
        return HttpResponse.json(mockHealthResponse);
      })
    );
  });

  describe('getReadyStatus', () => {
    it('returns health status when ready', async () => {
      const result = await getReadyStatus();

      expect(result.ready).toBe(true);
      expect(result.status).toBe('ready');
      expect(result.mode).toBe('normal');
      expect(result.components.database.connected).toBe(true);
    });

    it('returns unhealthy status when degraded', async () => {
      server.use(
        http.get('/ready', () => {
          return HttpResponse.json(
            {
              ready: false,
              status: 'not_ready',
              mode: 'degraded',
              components: {
                database: { status: 'healthy', connected: true },
                gitlab: {
                  status: 'degraded',
                  circuit_state: 'open',
                  failure_count: 5,
                  retry_after_seconds: 30,
                },
              },
            },
            { status: 503 }
          );
        })
      );

      const result = await getReadyStatus();

      expect(result.ready).toBe(false);
      expect(result.mode).toBe('degraded');
      expect(result.components.gitlab.circuit_state).toBe('open');
    });
  });
});
