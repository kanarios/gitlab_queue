/**
 * API-specific TypeScript types for GitLab Merge Queue Bot.
 *
 * These types mirror the backend response schemas defined in
 * backend/src/gitlab_queue/api/schemas.py
 */

import type { MergeRequest } from '../types';

// =============================================================================
// Error Handling
// =============================================================================

/**
 * API error type classification.
 */
export type ApiErrorType =
  | 'unauthorized'
  | 'not_found'
  | 'validation'
  | 'server_error'
  | 'network_error';

/**
 * Typed API error with optional HTTP status.
 */
export interface ApiError {
  type: ApiErrorType;
  message: string;
  status?: number;
}

/**
 * Discriminated union result type for API calls.
 * Ensures type-safe success/error handling.
 */
export type ApiResult<T> =
  | { success: true; data: T }
  | { success: false; error: ApiError };

// =============================================================================
// Pagination (matches backend PaginationSchema)
// =============================================================================

export interface Pagination {
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
}

// =============================================================================
// History Types (matches backend HistoryItemSchema)
// =============================================================================

/**
 * Paginated history response.
 * Matches PaginatedHistoryResponse from backend.
 */
export interface PaginatedHistoryResponse {
  items: MergeRequest[];
  pagination: Pagination;
}

// =============================================================================
// Analytics Types (matches backend analytics schemas)
// =============================================================================

/**
 * Analytics summary statistics.
 * Matches AnalyticsSummarySchema from backend.
 */
export interface AnalyticsSummary {
  total_processed: number;
  avg_wait_time_seconds: number;
  avg_processing_time_seconds: number;
  success_rate_percent: number;
  daily_throughput: number;
  period_days: number;
}

/**
 * Single hourly data point.
 * Matches HourlyDataPointSchema from backend.
 */
export interface HourlyDataPoint {
  timestamp: string;
  queue_depth: number;
  processed_count: number;
}

/**
 * Hourly analytics response.
 * Matches HourlyAnalyticsResponse from backend.
 */
export interface HourlyAnalyticsResponse {
  data: HourlyDataPoint[];
  hours: number;
}

/**
 * Outcome breakdown item.
 * Matches OutcomeSchema from backend.
 */
export interface Outcome {
  name: string;
  count: number;
  percentage: number;
}

/**
 * Outcomes breakdown response.
 * Matches OutcomesResponse from backend.
 */
export interface OutcomesResponse {
  outcomes: Outcome[];
  total: number;
  period_days: number;
}

/**
 * Failure reason item.
 * Matches FailureReasonSchema from backend.
 */
export interface FailureReason {
  reason: string;
  count: number;
  percentage: number;
}

/**
 * Failure reasons response.
 * Matches FailureReasonsResponse from backend.
 */
export interface FailureReasonsResponse {
  reasons: FailureReason[];
  total_failures: number;
  period_days: number;
}

// =============================================================================
// Queue Types
// =============================================================================

/**
 * Live queue statistics.
 */
export interface QueueStats {
  queue_length: number;
  processing_count: number;
  oldest_queued_at: string | null;
}
