/**
 * Tests for api/history.ts - History API client.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import { mockHistoryItem } from '../mocks/handlers';
import { getHistory, getHistoryItem } from '../../api/history';
import { setToken } from '../../auth/storage';

describe('api/history', () => {
  beforeEach(() => {
    localStorage.clear();
    setToken('test-token');
  });

  describe('getHistory', () => {
    it('returns paginated history', async () => {
      const result = await getHistory();

      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.items).toEqual([mockHistoryItem]);
        expect(result.data.pagination.total).toBe(1);
        expect(result.data.pagination.page).toBe(1);
        expect(result.data.pagination.total_pages).toBe(1);
      }
    });

    it('passes page parameter', async () => {
      let capturedPage: string | null = null;
      server.use(
        http.get('/api/history', ({ request }) => {
          const url = new URL(request.url);
          capturedPage = url.searchParams.get('page');
          return HttpResponse.json({
            items: [],
            pagination: {
              total: 0,
              page: 2,
              per_page: 10,
              total_pages: 0,
            },
          });
        })
      );

      await getHistory({ page: 2 });

      expect(capturedPage).toBe('2');
    });

    it('passes per_page parameter', async () => {
      let capturedPerPage: string | null = null;
      server.use(
        http.get('/api/history', ({ request }) => {
          const url = new URL(request.url);
          capturedPerPage = url.searchParams.get('per_page');
          return HttpResponse.json({
            items: [],
            pagination: {
              total: 0,
              page: 1,
              per_page: 20,
              total_pages: 0,
            },
          });
        })
      );

      await getHistory({ per_page: 20 });

      expect(capturedPerPage).toBe('20');
    });

    it('passes status filter', async () => {
      let capturedStatus: string | null = null;
      server.use(
        http.get('/api/history', ({ request }) => {
          const url = new URL(request.url);
          capturedStatus = url.searchParams.get('status');
          return HttpResponse.json({
            items: [],
            pagination: {
              total: 0,
              page: 1,
              per_page: 10,
              total_pages: 0,
            },
          });
        })
      );

      await getHistory({ status: 'merged' });

      expect(capturedStatus).toBe('merged');
    });

    it('passes search query', async () => {
      let capturedSearch: string | null = null;
      server.use(
        http.get('/api/history', ({ request }) => {
          const url = new URL(request.url);
          capturedSearch = url.searchParams.get('search');
          return HttpResponse.json({
            items: [],
            pagination: {
              total: 0,
              page: 1,
              per_page: 10,
              total_pages: 0,
            },
          });
        })
      );

      await getHistory({ search: 'test query' });

      expect(capturedSearch).toBe('test query');
    });

    it('passes all parameters together', async () => {
      let capturedParams: Record<string, string | null> = {};
      server.use(
        http.get('/api/history', ({ request }) => {
          const url = new URL(request.url);
          capturedParams = {
            page: url.searchParams.get('page'),
            per_page: url.searchParams.get('per_page'),
            status: url.searchParams.get('status'),
            search: url.searchParams.get('search'),
          };
          return HttpResponse.json({
            items: [],
            pagination: {
              total: 0,
              page: 1,
              per_page: 10,
              total_pages: 0,
            },
          });
        })
      );

      await getHistory({
        page: 2,
        per_page: 20,
        status: 'failed',
        search: 'bug fix',
      });

      expect(capturedParams).toEqual({
        page: '2',
        per_page: '20',
        status: 'failed',
        search: 'bug fix',
      });
    });

    it('returns error on server error', async () => {
      server.use(
        http.get('/api/history', () => {
          return HttpResponse.json(
            { detail: 'Internal server error' },
            { status: 500 }
          );
        })
      );

      const result = await getHistory();

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('server_error');
      }
    });
  });

  describe('getHistoryItem', () => {
    it('returns single history item', async () => {
      const result = await getHistoryItem(100);

      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.mr_iid).toBe(100);
      }
    });

    it('returns not_found error for non-existent item', async () => {
      server.use(
        http.get('/api/history/:iid', () => {
          return HttpResponse.json(
            { detail: 'MR not found' },
            { status: 404 }
          );
        })
      );

      const result = await getHistoryItem(999);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('not_found');
      }
    });
  });
});
