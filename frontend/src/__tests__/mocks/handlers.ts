/**
 * MSW request handlers for API mocking.
 */

import { http, HttpResponse } from 'msw';

// Mock data
export const mockUser = {
  id: 1,
  name: 'Test User',
  username: 'testuser',
  avatar_url: 'https://gitlab.com/avatar.png',
  email: 'test@example.com',
};

export const mockMergeRequest = {
  mr_iid: 42,
  title: 'Test MR',
  author: {
    name: 'Test User',
    username: 'testuser',
    avatar_url: 'https://gitlab.com/avatar.png',
  },
  status: 'queued' as const,
  labels: ['merge_queue'],
  is_hotfix: false,
  queued_at: '2025-01-01T10:00:00Z',
  started_at: null,
  finished_at: null,
  target_branch: 'main',
  pipeline: null,
  failure_reason: null,
};

export const mockQueueStats = {
  total: 3,
  queued: 2,
  processing: 1,
  avg_wait_time_seconds: 300,
};

export const mockHistoryItem = {
  ...mockMergeRequest,
  mr_iid: 100,
  status: 'merged' as const,
  finished_at: '2025-01-01T12:00:00Z',
};

export const mockAnalyticsSummary = {
  total_processed: 100,
  success_count: 90,
  failed_count: 10,
  avg_wait_time_seconds: 300,
  avg_processing_time_seconds: 600,
};

export const mockAnalyticsHourly = [
  { timestamp: '2025-01-01T10:00:00Z', queue_depth: 5, processed_count: 3 },
  { timestamp: '2025-01-01T11:00:00Z', queue_depth: 4, processed_count: 4 },
];

export const mockAnalyticsOutcomes = {
  merged: 90,
  failed: 5,
  conflict: 3,
  timeout: 2,
};

export const mockFailureReasons = [
  { reason: 'pipeline_failed', count: 5, percentage: 50 },
  { reason: 'conflict', count: 3, percentage: 30 },
  { reason: 'timeout', count: 2, percentage: 20 },
];

// Default handlers
export const handlers = [
  // Auth endpoints
  http.get('/auth/me', () => {
    return HttpResponse.json(mockUser);
  }),

  http.post('/auth/logout', () => {
    return new HttpResponse(null, { status: 204 });
  }),

  http.get('/auth/callback', ({ request }) => {
    const url = new URL(request.url);
    const code = url.searchParams.get('code');
    const state = url.searchParams.get('state');

    if (!code || !state) {
      return HttpResponse.json(
        { detail: 'Missing code or state parameter' },
        { status: 400 }
      );
    }

    return HttpResponse.json({
      access_token: 'mock-jwt-token',
      token_type: 'bearer',
      user: mockUser,
    });
  }),

  http.post('/auth/token', ({ request }) => {
    const url = new URL(request.url);
    const code = url.searchParams.get('code');
    const state = url.searchParams.get('state');

    if (!code || !state) {
      return HttpResponse.json(
        { detail: 'Missing code or state parameter' },
        { status: 400 }
      );
    }

    if (code === 'invalid-code') {
      return HttpResponse.json(
        { detail: 'Invalid authorization code' },
        { status: 400 }
      );
    }

    if (state === 'invalid-state') {
      return HttpResponse.json(
        { detail: 'Invalid state parameter' },
        { status: 400 }
      );
    }

    return HttpResponse.json({
      access_token: 'mock-jwt-token',
      token_type: 'bearer',
      user: mockUser,
    });
  }),

  // Queue endpoints
  http.get('/api/queue', () => {
    return HttpResponse.json([mockMergeRequest]);
  }),

  http.get('/api/queue/stats', () => {
    return HttpResponse.json(mockQueueStats);
  }),

  // History endpoints
  http.get('/api/history', ({ request }) => {
    const url = new URL(request.url);
    const page = parseInt(url.searchParams.get('page') ?? '1');
    const perPage = parseInt(url.searchParams.get('per_page') ?? '10');

    return HttpResponse.json({
      items: [mockHistoryItem],
      pagination: {
        page,
        per_page: perPage,
        total: 1,
        total_pages: 1,
      },
    });
  }),

  http.get('/api/history/:iid', ({ params }) => {
    const iid = parseInt(params.iid as string);
    return HttpResponse.json({ ...mockHistoryItem, mr_iid: iid });
  }),

  // Analytics endpoints
  http.get('/api/analytics/summary', () => {
    return HttpResponse.json(mockAnalyticsSummary);
  }),

  http.get('/api/analytics/hourly', () => {
    return HttpResponse.json(mockAnalyticsHourly);
  }),

  http.get('/api/analytics/outcomes', () => {
    return HttpResponse.json(mockAnalyticsOutcomes);
  }),

  http.get('/api/analytics/failure-reasons', () => {
    return HttpResponse.json(mockFailureReasons);
  }),

  // Health endpoint
  http.get('/ready', () => {
    return HttpResponse.json({ status: 'ok', database: 'ok', gitlab: 'ok' });
  }),
];
