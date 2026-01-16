/**
 * API client layer for GitLab Merge Queue Bot.
 *
 * This module provides a type-safe, consistent API client with:
 * - JWT authentication (automatic header injection)
 * - 401 handling (auto logout + redirect)
 * - Request cancellation via AbortController
 * - Typed error handling
 *
 * @example
 * ```typescript
 * import { getHistory, getQueue, getSummary } from './api';
 *
 * // Fetch history with pagination
 * const history = await getHistory({ page: 1, per_page: 20 });
 *
 * // Fetch live queue
 * const queue = await getQueue();
 *
 * // Fetch analytics
 * const summary = await getSummary({ days: 7 });
 * ```
 */

// Client utilities
export { apiFetch, buildUrl } from './client';

// History API
export { getHistory, getHistoryItem } from './history';
export type { GetHistoryParams } from './history';

// Analytics API
export { getSummary, getHourly, getOutcomes, getFailureReasons } from './analytics';
export type { AnalyticsParams, HourlyParams } from './analytics';

// Queue API
export { getQueue, getQueueStats } from './queue';

// WebSocket
export { WebSocketManager, wsManager } from './websocket';

// Types
export type {
  ApiError,
  ApiErrorType,
  ApiResult,
  Pagination,
  PaginatedHistoryResponse,
  AnalyticsSummary,
  HourlyDataPoint,
  HourlyAnalyticsResponse,
  Outcome,
  OutcomesResponse,
  FailureReason,
  FailureReasonsResponse,
  QueueStats,
} from './types';
