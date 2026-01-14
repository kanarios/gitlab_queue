/**
 * Queue API client for GitLab Merge Queue Bot.
 *
 * Provides functions to fetch the live queue state
 * and queue statistics.
 */

import { apiFetch } from './client';
import type { ApiResult, QueueStats } from './types';
import type { MergeRequest } from '../types';

/**
 * Get current live queue.
 *
 * Returns all MRs currently in the queue with their
 * real-time status (queued, rebasing, testing, merging).
 *
 * @param signal - Optional AbortSignal for cancellation
 * @returns Array of MRs in the queue
 *
 * @example
 * ```typescript
 * const result = await getQueue();
 * if (result.success) {
 *   console.log(`${result.data.length} MRs in queue`);
 *   result.data.forEach(mr => {
 *     console.log(`!${mr.mr_iid}: ${mr.status}`);
 *   });
 * }
 * ```
 */
export async function getQueue(signal?: AbortSignal): Promise<ApiResult<MergeRequest[]>> {
  return apiFetch<MergeRequest[]>('/api/queue', { signal });
}

/**
 * Get queue statistics.
 *
 * Returns aggregate statistics about the current queue:
 * - Queue length (total MRs waiting)
 * - Processing count (MRs being actively processed)
 * - Oldest queued timestamp
 *
 * @param signal - Optional AbortSignal for cancellation
 * @returns Queue statistics
 *
 * @example
 * ```typescript
 * const result = await getQueueStats();
 * if (result.success) {
 *   console.log(`Queue: ${result.data.queue_length} MRs`);
 *   console.log(`Processing: ${result.data.processing_count}`);
 * }
 * ```
 */
export async function getQueueStats(signal?: AbortSignal): Promise<ApiResult<QueueStats>> {
  return apiFetch<QueueStats>('/api/queue/stats', { signal });
}
