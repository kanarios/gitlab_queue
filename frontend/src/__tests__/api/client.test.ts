/**
 * Tests for api/client.ts - Base API client.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import { apiFetch, buildUrl } from '../../api/client';
import { setToken } from '../../auth/storage';

describe('api/client', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    // Reset window.location.href mock
    window.location.href = 'http://localhost:3000';
  });

  describe('apiFetch', () => {
    it('returns successful response data', async () => {
      server.use(
        http.get('/api/test', () => {
          return HttpResponse.json({ message: 'success' });
        })
      );

      const result = await apiFetch<{ message: string }>('/api/test');

      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data).toEqual({ message: 'success' });
      }
    });

    it('adds Authorization header when token exists', async () => {
      setToken('test-jwt-token');

      const capturedHeaders: { value: Headers | null } = { value: null };
      server.use(
        http.get('/api/test', ({ request }) => {
          capturedHeaders.value = request.headers;
          return HttpResponse.json({});
        })
      );

      await apiFetch('/api/test');

      expect(capturedHeaders.value?.get('Authorization')).toBe(
        'Bearer test-jwt-token'
      );
    });

    it('does not add Authorization header when no token', async () => {
      const capturedHeaders: { value: Headers | null } = { value: null };
      server.use(
        http.get('/api/test', ({ request }) => {
          capturedHeaders.value = request.headers;
          return HttpResponse.json({});
        })
      );

      await apiFetch('/api/test');

      expect(capturedHeaders.value?.get('Authorization')).toBeNull();
    });

    it('sets Content-Type to application/json', async () => {
      const capturedHeaders: { value: Headers | null } = { value: null };
      server.use(
        http.get('/api/test', ({ request }) => {
          capturedHeaders.value = request.headers;
          return HttpResponse.json({});
        })
      );

      await apiFetch('/api/test');

      expect(capturedHeaders.value?.get('Content-Type')).toBe('application/json');
    });

    it('returns unauthorized error on 401 and clears token', async () => {
      setToken('expired-token');
      server.use(
        http.get('/api/test', () => {
          return HttpResponse.json(
            { detail: 'Session expired' },
            { status: 401 }
          );
        })
      );

      const result = await apiFetch('/api/test');

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('unauthorized');
        expect(result.error.status).toBe(401);
      }
      // Token should be cleared
      expect(localStorage.getItem('gitlab_queue_token')).toBeNull();
      // Should redirect to login
      expect(window.location.href).toBe('/login');
    });

    it('returns not_found error on 404', async () => {
      server.use(
        http.get('/api/test', () => {
          return HttpResponse.json(
            { detail: 'Resource not found' },
            { status: 404 }
          );
        })
      );

      const result = await apiFetch('/api/test');

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('not_found');
        expect(result.error.status).toBe(404);
      }
    });

    it('returns validation error on 422', async () => {
      server.use(
        http.get('/api/test', () => {
          return HttpResponse.json(
            { detail: 'Validation failed' },
            { status: 422 }
          );
        })
      );

      const result = await apiFetch('/api/test');

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('validation');
        expect(result.error.status).toBe(422);
      }
    });

    it('returns server_error on 5xx', async () => {
      server.use(
        http.get('/api/test', () => {
          return HttpResponse.json(
            { detail: 'Internal server error' },
            { status: 500 }
          );
        })
      );

      const result = await apiFetch('/api/test');

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('server_error');
        expect(result.error.status).toBe(500);
      }
    });

    it('returns network_error on fetch failure', async () => {
      server.use(
        http.get('/api/test', () => {
          return HttpResponse.error();
        })
      );

      const result = await apiFetch('/api/test');

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('network_error');
      }
    });

    it('handles request cancellation via AbortController', async () => {
      server.use(
        http.get('/api/test', async () => {
          // Simulate a slow response
          await new Promise((resolve) => setTimeout(resolve, 1000));
          return HttpResponse.json({});
        })
      );

      const controller = new AbortController();

      const resultPromise = apiFetch('/api/test', {
        signal: controller.signal,
      });

      // Cancel immediately
      controller.abort();

      const result = await resultPromise;

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('network_error');
        expect(result.error.message).toBe('Request cancelled');
      }
    });

    it('passes custom headers', async () => {
      const capturedHeaders: { value: Headers | null } = { value: null };
      server.use(
        http.get('/api/test', ({ request }) => {
          capturedHeaders.value = request.headers;
          return HttpResponse.json({});
        })
      );

      await apiFetch('/api/test', {
        headers: {
          'X-Custom-Header': 'custom-value',
        },
      });

      expect(capturedHeaders.value?.get('X-Custom-Header')).toBe('custom-value');
    });

    it('supports POST requests with body', async () => {
      let capturedBody: unknown = null;
      server.use(
        http.post('/api/test', async ({ request }) => {
          capturedBody = await request.json();
          return HttpResponse.json({ id: 1 });
        })
      );

      const result = await apiFetch<{ id: number }>('/api/test', {
        method: 'POST',
        body: JSON.stringify({ name: 'test' }),
      });

      expect(result.success).toBe(true);
      expect(capturedBody).toEqual({ name: 'test' });
    });

    it('handles error response without detail field', async () => {
      server.use(
        http.get('/api/test', () => {
          return HttpResponse.json({ error: 'Something went wrong' }, { status: 400 });
        })
      );

      const result = await apiFetch('/api/test');

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.message).toBe('Request failed');
      }
    });

    it('handles error response with message field', async () => {
      server.use(
        http.get('/api/test', () => {
          return HttpResponse.json({ message: 'Custom error message' }, { status: 400 });
        })
      );

      const result = await apiFetch('/api/test');

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.message).toBe('Custom error message');
      }
    });
  });

  describe('buildUrl', () => {
    it('returns endpoint when no params', () => {
      const url = buildUrl('/api/test', {});
      expect(url).toBe('/api/test');
    });

    it('adds query params to URL', () => {
      const url = buildUrl('/api/test', { page: 1, status: 'merged' });
      expect(url).toBe('/api/test?page=1&status=merged');
    });

    it('filters out undefined values', () => {
      const url = buildUrl('/api/test', {
        page: 1,
        status: undefined,
        search: 'query',
      });
      expect(url).toBe('/api/test?page=1&search=query');
    });

    it('filters out null values', () => {
      const url = buildUrl('/api/test', {
        page: 1,
        status: null,
        search: 'query',
      });
      expect(url).toBe('/api/test?page=1&search=query');
    });

    it('converts numbers to strings', () => {
      const url = buildUrl('/api/test', { page: 1, limit: 10 });
      expect(url).toBe('/api/test?page=1&limit=10');
    });

    it('converts booleans to strings', () => {
      const url = buildUrl('/api/test', { active: true, archived: false });
      expect(url).toBe('/api/test?active=true&archived=false');
    });
  });
});
