/**
 * Tests for auth/api.ts - OAuth authentication API.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import { mockUser } from '../mocks/handlers';
import {
  redirectToLogin,
  handleCallback,
  getCurrentUser,
  logout,
  getAuthHeader,
} from '../../auth/api';
import { setToken, clearToken } from '../../auth/storage';

describe('auth/api', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  describe('redirectToLogin', () => {
    it('redirects to /auth/login', () => {
      redirectToLogin();
      expect(window.location.href).toBe('/auth/login');
    });
  });

  describe('handleCallback', () => {
    it('exchanges code for token and returns user', async () => {
      const result = await handleCallback('valid-code', 'valid-state');

      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.user).toEqual(mockUser);
      }
    });

    it('stores the token on success', async () => {
      await handleCallback('valid-code', 'valid-state');
      expect(localStorage.getItem('gitlab_queue_token')).toBe('mock-jwt-token');
    });

    it('returns error for invalid code', async () => {
      server.use(
        http.get('/auth/callback', () => {
          return HttpResponse.json(
            { detail: 'Invalid authorization code' },
            { status: 400 }
          );
        })
      );

      const result = await handleCallback('invalid-code', 'valid-state');

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('access_denied');
      }
    });

    it('returns error for invalid state', async () => {
      server.use(
        http.get('/auth/callback', () => {
          return HttpResponse.json(
            { detail: 'Invalid state parameter' },
            { status: 400 }
          );
        })
      );

      const result = await handleCallback('valid-code', 'invalid-state');

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('invalid_state');
      }
    });

    it('returns network error on fetch failure', async () => {
      server.use(
        http.get('/auth/callback', () => {
          return HttpResponse.error();
        })
      );

      const result = await handleCallback('code', 'state');

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('network_error');
      }
    });
  });

  describe('getCurrentUser', () => {
    it('returns error when no token exists', async () => {
      const result = await getCurrentUser();

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('token_expired');
        expect(result.error.message).toBe('No authentication token');
      }
    });

    it('returns user when token is valid', async () => {
      setToken('valid-token');

      const result = await getCurrentUser();

      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.user).toEqual(mockUser);
      }
    });

    it('clears token and returns error on 401', async () => {
      setToken('expired-token');
      server.use(
        http.get('/auth/me', () => {
          return HttpResponse.json(
            { detail: 'Token expired' },
            { status: 401 }
          );
        })
      );

      const result = await getCurrentUser();

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('token_expired');
      }
      expect(localStorage.getItem('gitlab_queue_token')).toBeNull();
    });

    it('returns error on 403 (no project access)', async () => {
      setToken('valid-token');
      server.use(
        http.get('/auth/me', () => {
          return HttpResponse.json(
            { detail: 'No access to project' },
            { status: 403 }
          );
        })
      );

      const result = await getCurrentUser();

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('no_access');
      }
    });

    it('returns network error on fetch failure', async () => {
      setToken('valid-token');
      server.use(
        http.get('/auth/me', () => {
          return HttpResponse.error();
        })
      );

      const result = await getCurrentUser();

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('network_error');
      }
    });
  });

  describe('logout', () => {
    it('clears the token immediately', async () => {
      setToken('test-token');
      await logout();
      expect(localStorage.getItem('gitlab_queue_token')).toBeNull();
    });

    it('does not throw when logout endpoint fails', async () => {
      setToken('test-token');
      server.use(
        http.post('/auth/logout', () => {
          return HttpResponse.error();
        })
      );

      // Should not throw
      await expect(logout()).resolves.toBeUndefined();
    });

    it('works without token', async () => {
      // Should not throw when no token exists
      await expect(logout()).resolves.toBeUndefined();
    });
  });

  describe('getAuthHeader', () => {
    it('returns null when no token exists', () => {
      expect(getAuthHeader()).toBeNull();
    });

    it('returns Authorization header when token exists', () => {
      setToken('test-token');
      expect(getAuthHeader()).toEqual({ Authorization: 'Bearer test-token' });
    });
  });
});
