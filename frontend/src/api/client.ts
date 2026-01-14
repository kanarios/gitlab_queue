/**
 * Base API client with JWT authentication for GitLab Merge Queue Bot.
 *
 * Features:
 * - Type-safe fetch wrapper
 * - Automatic JWT header injection
 * - 401 → auto logout and redirect
 * - AbortController support for request cancellation
 * - Typed error mapping
 */

import { getToken, clearToken } from '../auth/storage';
import type { ApiError, ApiResult } from './types';

const API_BASE = ''; // Vite proxy handles /api/* routes

/**
 * Map HTTP status code to typed ApiError.
 */
function mapStatusToError(status: number, detail: string): ApiError {
  if (status === 401) {
    return { type: 'unauthorized', message: detail, status };
  }
  if (status === 404) {
    return { type: 'not_found', message: detail, status };
  }
  if (status === 422) {
    return { type: 'validation', message: detail, status };
  }
  return { type: 'server_error', message: detail, status };
}

/**
 * Type-safe fetch wrapper with JWT authentication.
 *
 * Handles:
 * - Automatic Authorization header from stored token
 * - 401 responses → clear token + redirect to login
 * - AbortController support via signal parameter
 * - JSON parsing and error mapping
 *
 * @param endpoint - API endpoint (e.g., '/api/history')
 * @param options - Fetch options including optional AbortSignal
 * @returns Typed ApiResult with success/error discriminated union
 *
 * @example
 * ```typescript
 * const result = await apiFetch<MergeRequest[]>('/api/queue');
 * if (result.success) {
 *   console.log(result.data);
 * } else {
 *   console.error(result.error.message);
 * }
 * ```
 */
export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit & { signal?: AbortSignal } = {}
): Promise<ApiResult<T>> {
  const token = getToken();

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (token) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  }

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    // Handle 401 - clear token and redirect to login
    if (response.status === 401) {
      clearToken();
      window.location.href = '/login';
      return {
        success: false,
        error: { type: 'unauthorized', message: 'Session expired', status: 401 },
      };
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
      const message = errorData.detail || errorData.message || 'Request failed';
      return {
        success: false,
        error: mapStatusToError(response.status, message),
      };
    }

    const data: T = await response.json();
    return { success: true, data };
  } catch (error) {
    // Handle AbortError specifically (request cancelled)
    if (error instanceof Error && error.name === 'AbortError') {
      return {
        success: false,
        error: { type: 'network_error', message: 'Request cancelled' },
      };
    }

    return {
      success: false,
      error: {
        type: 'network_error',
        message: error instanceof Error ? error.message : 'Network request failed',
      },
    };
  }
}

/**
 * Build URL with query parameters.
 *
 * Filters out undefined and null values.
 *
 * @param endpoint - Base endpoint path
 * @param params - Query parameters object
 * @returns URL string with query parameters
 *
 * @example
 * ```typescript
 * const url = buildUrl('/api/history', { page: 1, status: 'merged', search: undefined });
 * // Returns: '/api/history?page=1&status=merged'
 * ```
 */
export function buildUrl(
  endpoint: string,
  params: Record<string, string | number | boolean | undefined | null>
): string {
  const url = new URL(endpoint, window.location.origin);

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      url.searchParams.set(key, String(value));
    }
  });

  return url.pathname + url.search;
}
