/**
 * Analytics API client for GitLab Merge Queue Bot.
 *
 * Provides functions to fetch queue analytics including
 * summary statistics, hourly trends, outcomes breakdown,
 * and failure reason analysis.
 */

import { apiFetch, buildUrl } from './client';
import type {
  ApiResult,
  AnalyticsSummary,
  HourlyAnalyticsResponse,
  OutcomesResponse,
  FailureReasonsResponse,
} from './types';

/**
 * Parameters for analytics API calls that use day-based periods.
 */
export interface AnalyticsParams {
  /** Number of days to include (default: 7, max: 365) */
  days?: number;
  /** AbortSignal for request cancellation */
  signal?: AbortSignal;
}

/**
 * Parameters for hourly analytics API call.
 */
export interface HourlyParams {
  /** Number of hours to include (default: 24, max: 168 = 7 days) */
  hours?: number;
  /** AbortSignal for request cancellation */
  signal?: AbortSignal;
}

/**
 * Get analytics summary for the specified period.
 *
 * Returns aggregate statistics including:
 * - Total MRs processed
 * - Average wait time and processing time
 * - Success rate percentage
 * - Daily throughput
 *
 * @param params - Query parameters and options
 * @returns Analytics summary for the period
 *
 * @example
 * ```typescript
 * // Last 7 days (default)
 * const result = await getSummary();
 *
 * // Last 30 days
 * const result = await getSummary({ days: 30 });
 * ```
 */
export async function getSummary(
  params: AnalyticsParams = {}
): Promise<ApiResult<AnalyticsSummary>> {
  const { signal, ...queryParams } = params;
  const url = buildUrl('/api/analytics/summary', queryParams);
  return apiFetch<AnalyticsSummary>(url, { signal });
}

/**
 * Get hourly analytics data points.
 *
 * Returns time-series data for:
 * - Queue depth at each hour
 * - MRs processed per hour
 *
 * @param params - Query parameters and options
 * @returns Array of hourly data points
 *
 * @example
 * ```typescript
 * // Last 24 hours (default)
 * const result = await getHourly();
 *
 * // Last 72 hours
 * const result = await getHourly({ hours: 72 });
 * ```
 */
export async function getHourly(
  params: HourlyParams = {}
): Promise<ApiResult<HourlyAnalyticsResponse>> {
  const { signal, ...queryParams } = params;
  const url = buildUrl('/api/analytics/hourly', queryParams);
  return apiFetch<HourlyAnalyticsResponse>(url, { signal });
}

/**
 * Get outcome breakdown for the specified period.
 *
 * Returns counts and percentages for:
 * - merged: Successfully merged MRs
 * - failed: Pipeline failures
 * - conflict: Rebase conflicts
 * - timeout: Timeout exceeded
 *
 * @param params - Query parameters and options
 * @returns Outcomes breakdown with counts and percentages
 *
 * @example
 * ```typescript
 * const result = await getOutcomes({ days: 7 });
 * if (result.success) {
 *   result.data.outcomes.forEach(o => {
 *     console.log(`${o.name}: ${o.count} (${o.percentage}%)`);
 *   });
 * }
 * ```
 */
export async function getOutcomes(
  params: AnalyticsParams = {}
): Promise<ApiResult<OutcomesResponse>> {
  const { signal, ...queryParams } = params;
  const url = buildUrl('/api/analytics/outcomes', queryParams);
  return apiFetch<OutcomesResponse>(url, { signal });
}

/**
 * Get failure reason breakdown for the specified period.
 *
 * Returns detailed breakdown of why MRs failed:
 * - Specific error messages
 * - Failure counts and percentages
 *
 * @param params - Query parameters and options
 * @returns Failure reasons with counts and percentages
 *
 * @example
 * ```typescript
 * const result = await getFailureReasons({ days: 30 });
 * if (result.success) {
 *   result.data.reasons.forEach(r => {
 *     console.log(`${r.reason}: ${r.count} failures`);
 *   });
 * }
 * ```
 */
export async function getFailureReasons(
  params: AnalyticsParams = {}
): Promise<ApiResult<FailureReasonsResponse>> {
  const { signal, ...queryParams } = params;
  const url = buildUrl('/api/analytics/failure-reasons', queryParams);
  return apiFetch<FailureReasonsResponse>(url, { signal });
}
