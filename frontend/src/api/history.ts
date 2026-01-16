/**
 * History API client for GitLab Merge Queue Bot.
 *
 * Provides functions to fetch completed MR history with
 * pagination, filtering, and search capabilities.
 */

import { apiFetch, buildUrl } from './client';
import type { ApiResult, PaginatedHistoryResponse } from './types';
import type { MergeRequest } from '../types';

/**
 * Parameters for getHistory API call.
 */
export interface GetHistoryParams {
  /** Page number (1-indexed, default: 1) */
  page?: number;
  /** Items per page (default: 20, max: 100) */
  per_page?: number;
  /** Filter by final status (merged, failed, conflict, timeout) */
  status?: string;
  /** Filter MRs finished on or after this date (ISO date string) */
  date_from?: string;
  /** Filter MRs finished on or before this date (ISO date string) */
  date_to?: string;
  /** Search by title, author username, or MR IID */
  search?: string;
  /** AbortSignal for request cancellation */
  signal?: AbortSignal;
}

/**
 * Get paginated history of completed MRs.
 *
 * @param params - Query parameters and options
 * @returns Paginated list of completed MRs
 *
 * @example
 * ```typescript
 * // Basic usage
 * const result = await getHistory({ page: 1, per_page: 20 });
 *
 * // With filters
 * const result = await getHistory({
 *   status: 'merged',
 *   date_from: '2025-01-01',
 *   search: 'feature',
 * });
 *
 * // With cancellation
 * const controller = new AbortController();
 * const result = await getHistory({ signal: controller.signal });
 * controller.abort(); // Cancel request
 * ```
 */
export async function getHistory(
  params: GetHistoryParams = {}
): Promise<ApiResult<PaginatedHistoryResponse>> {
  const { signal, ...queryParams } = params;
  const url = buildUrl('/api/history', queryParams);
  return apiFetch<PaginatedHistoryResponse>(url, { signal });
}

/**
 * Get a single MR from history by its IID.
 *
 * @param iid - The MR's internal ID
 * @param signal - Optional AbortSignal for cancellation
 * @returns The MR history item or 404 error
 *
 * @example
 * ```typescript
 * const result = await getHistoryItem(1042);
 * if (result.success) {
 *   console.log(result.data.title);
 * } else if (result.error.type === 'not_found') {
 *   console.log('MR not found in history');
 * }
 * ```
 */
export async function getHistoryItem(
  iid: number,
  signal?: AbortSignal
): Promise<ApiResult<MergeRequest>> {
  return apiFetch<MergeRequest>(`/api/history/${iid}`, { signal });
}
