/**
 * Tests for auth/storage.ts - Token storage utilities.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { getToken, setToken, clearToken, hasToken } from '../../auth/storage';

describe('auth/storage', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe('getToken', () => {
    it('returns null when no token is stored', () => {
      expect(getToken()).toBeNull();
    });

    it('returns the stored token', () => {
      localStorage.setItem('gitlab_queue_token', 'test-token-123');
      expect(getToken()).toBe('test-token-123');
    });
  });

  describe('setToken', () => {
    it('stores the token in localStorage', () => {
      setToken('new-token-456');
      expect(localStorage.getItem('gitlab_queue_token')).toBe('new-token-456');
    });

    it('overwrites existing token', () => {
      setToken('token-1');
      setToken('token-2');
      expect(localStorage.getItem('gitlab_queue_token')).toBe('token-2');
    });
  });

  describe('clearToken', () => {
    it('removes the token from localStorage', () => {
      localStorage.setItem('gitlab_queue_token', 'test-token');
      clearToken();
      expect(localStorage.getItem('gitlab_queue_token')).toBeNull();
    });

    it('does not throw when token does not exist', () => {
      expect(() => clearToken()).not.toThrow();
    });
  });

  describe('hasToken', () => {
    it('returns false when no token is stored', () => {
      expect(hasToken()).toBe(false);
    });

    it('returns true when a token is stored', () => {
      localStorage.setItem('gitlab_queue_token', 'test-token');
      expect(hasToken()).toBe(true);
    });
  });
});
