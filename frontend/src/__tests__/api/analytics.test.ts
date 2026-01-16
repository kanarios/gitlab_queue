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
    it('returns summary data', async () => {
      const result = await getSummary();

      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toEqual(mockAnalyticsSummary);
      }
    });

    it('returns error on server error', async () => {
      server.use(
        http.get('/api/analytics/summary', () => {
          return HttpResponse.json(
            { detail: 'Internal server error' },
            { status: 500 }
          );
        })
      );

      const result = await getSummary();

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('server_error');
      }
    });
  });

  describe('getHourly', () => {
    it('returns hourly data', async () => {
      const result = await getHourly();

      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toEqual(mockAnalyticsHourly);
      }
    });

    it('passes hours parameter', async () => {
      let capturedHours: string | null = null;
      server.use(
        http.get('/api/analytics/hourly', ({ request }) => {
          const url = new URL(request.url);
          capturedHours = url.searchParams.get('hours');
          return HttpResponse.json([]);
        })
      );

      await getHourly({ hours: 48 });

      expect(capturedHours).toBe('48');
    });

    it('returns error on server error', async () => {
      server.use(
        http.get('/api/analytics/hourly', () => {
          return HttpResponse.json(
            { detail: 'Internal server error' },
            { status: 500 }
          );
        })
      );

      const result = await getHourly();

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('server_error');
      }
    });
  });

  describe('getOutcomes', () => {
    it('returns outcomes data', async () => {
      const result = await getOutcomes();

      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toEqual(mockAnalyticsOutcomes);
      }
    });

    it('returns error on server error', async () => {
      server.use(
        http.get('/api/analytics/outcomes', () => {
          return HttpResponse.json(
            { detail: 'Internal server error' },
            { status: 500 }
          );
        })
      );

      const result = await getOutcomes();

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('server_error');
      }
    });
  });

  describe('getFailureReasons', () => {
    it('returns failure reasons data', async () => {
      const result = await getFailureReasons();

      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toEqual(mockFailureReasons);
      }
    });

    it('returns error on server error', async () => {
      server.use(
        http.get('/api/analytics/failure-reasons', () => {
          return HttpResponse.json(
            { detail: 'Internal server error' },
            { status: 500 }
          );
        })
      );

      const result = await getFailureReasons();

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('server_error');
      }
    });
  });
});
