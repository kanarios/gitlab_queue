/**
 * Tests for api/config.ts - Project config API.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import { getProjectConfig } from '../../api/config';

const mockConfigResponse = {
  project_web_url: 'https://gitlab.example.com/group/project',
};

describe('api/config', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    server.use(
      http.get('/api/config', () => {
        return HttpResponse.json(mockConfigResponse);
      })
    );
  });

  describe('getProjectConfig', () => {
    it('returns project config on success', async () => {
      const result = await getProjectConfig();

      expect(result).toEqual({ success: true, data: mockConfigResponse });
    });

    it('returns error on server error', async () => {
      server.use(
        http.get('/api/config', () => {
          return HttpResponse.json(
            { detail: 'Internal server error' },
            { status: 500 }
          );
        })
      );

      const result = await getProjectConfig();

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('server_error');
      }
    });

    it('forwards AbortSignal to fetch', async () => {
      const controller = new AbortController();
      controller.abort();

      const result = await getProjectConfig(controller.signal);

      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error.type).toBe('network_error');
        expect(result.error.message).toBe('Request cancelled');
      }
    });
  });
});
