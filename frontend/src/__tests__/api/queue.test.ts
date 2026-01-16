/**
 * Tests for api/queue.ts - Queue API client.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import { mockMergeRequest, mockQueueStats } from '../mocks/handlers';
import { getQueue, getQueueStats } from '../../api/queue';
import { setToken } from '../../auth/storage';

describe('api/queue', () => {
  beforeEach(() => {
    localStorage.clear();
    setToken('test-token');
  });

  describe('getQueue', () => {
    it('returns queue data', async () => {
      const result = await getQueue();

      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toEqual([mockMergeRequest]);
      }
    });

    it('returns empty array for empty queue', async () => {
      server.use(
        http.get('/api/queue', () => {
          return HttpResponse.json([]);
        })
      );

      const result = await getQueue();

      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toEqual([]);
      }
    });

    it('returns error on server error', async () => {
      server.use(
        http.get('/api/queue', () => {
          return HttpResponse.json(
            { detail: 'Internal server error' },
            { status: 500 }
          );
        })
      );

      const result = await getQueue();

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('server_error');
      }
    });
  });

  describe('getQueueStats', () => {
    it('returns queue stats', async () => {
      const result = await getQueueStats();

      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toEqual(mockQueueStats);
      }
    });

    it('returns error on server error', async () => {
      server.use(
        http.get('/api/queue/stats', () => {
          return HttpResponse.json(
            { detail: 'Internal server error' },
            { status: 500 }
          );
        })
      );

      const result = await getQueueStats();

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('server_error');
      }
    });
  });
});
