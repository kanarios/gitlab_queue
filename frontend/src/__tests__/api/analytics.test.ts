/**
 * Tests for api/analytics.ts - Analytics API client.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import {
  mockAnalyticsSummary,
  mockAnalyticsHourly,
  mockAnalyticsOutcomes,
  mockFailureReasons,
} from '../mocks/handlers';
import {
  getSummary,
  getHourly,
  getOutcomes,
  getFailureReasons,
} from '../../api/analytics';
import { setToken } from '../../auth/storage';

describe('api/analytics', () => {
  beforeEach(() => {
    localStorage.clear();
    setToken('test-token');
  });

  describe('getSummary', () => {
    it('uses the selected project in the analytics path', async () => {
      let requestPath = '';
      server.use(
        http.get('/api/projects/:projectId/analytics/summary', ({ request }) => {
          requestPath = new URL(request.url).pathname;
          return HttpResponse.json(mockAnalyticsSummary);
        })
      );

      await getSummary(81);

      expect(requestPath).toBe('/api/projects/81/analytics/summary');
    });

    it('returns summary data', async () => {
      const result = await getSummary(1);

      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toEqual(mockAnalyticsSummary);
      }
    });

    it('returns error on server error', async () => {
      server.use(
        http.get('/api/projects/1/analytics/summary', () => {
          return HttpResponse.json(
            { detail: 'Internal server error' },
            { status: 500 }
          );
        })
      );

      const result = await getSummary(1);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('server_error');
      }
    });
  });

  describe('getHourly', () => {
    it('returns hourly data', async () => {
      const result = await getHourly(1);

      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toEqual(mockAnalyticsHourly);
      }
    });

    it('passes hours parameter', async () => {
      let capturedHours: string | null = null;
      server.use(
        http.get('/api/projects/1/analytics/hourly', ({ request }) => {
          const url = new URL(request.url);
          capturedHours = url.searchParams.get('hours');
          return HttpResponse.json([]);
        })
      );

      await getHourly(1, { hours: 48 });

      expect(capturedHours).toBe('48');
    });

    it('returns error on server error', async () => {
      server.use(
        http.get('/api/projects/1/analytics/hourly', () => {
          return HttpResponse.json(
            { detail: 'Internal server error' },
            { status: 500 }
          );
        })
      );

      const result = await getHourly(1);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('server_error');
      }
    });
  });

  describe('getOutcomes', () => {
    it('returns outcomes data', async () => {
      const result = await getOutcomes(1);

      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toEqual(mockAnalyticsOutcomes);
      }
    });

    it('returns error on server error', async () => {
      server.use(
        http.get('/api/projects/1/analytics/outcomes', () => {
          return HttpResponse.json(
            { detail: 'Internal server error' },
            { status: 500 }
          );
        })
      );

      const result = await getOutcomes(1);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('server_error');
      }
    });
  });

  describe('getFailureReasons', () => {
    it('returns failure reasons data', async () => {
      const result = await getFailureReasons(1);

      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toEqual(mockFailureReasons);
      }
    });

    it('returns error on server error', async () => {
      server.use(
        http.get('/api/projects/1/analytics/failure-reasons', () => {
          return HttpResponse.json(
            { detail: 'Internal server error' },
            { status: 500 }
          );
        })
      );

      const result = await getFailureReasons(1);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('server_error');
      }
    });
  });
});
