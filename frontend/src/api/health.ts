/**
 * Health check API client.
 *
 * Fetches application health status from the backend /ready endpoint.
 */

/** Database component health status. */
export interface DatabaseHealth {
  status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
  connected: boolean;
}

/** GitLab component health status. */
export interface GitLabHealth {
  status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
  circuit_state?: string;
  failure_count?: number;
  retry_after_seconds?: number | null;
}

/** Health check response from /ready endpoint. */
export interface ReadyResponse {
  ready: boolean;
  status: 'ready' | 'not_ready';
  mode: 'normal' | 'degraded' | 'unhealthy';
  components: {
    database: DatabaseHealth;
    gitlab: GitLabHealth;
  };
}

/**
 * Fetch application readiness status.
 *
 * Note: The /ready endpoint returns 503 when not ready, but still
 * includes a JSON body with detailed status information.
 */
export async function getReadyStatus(): Promise<ReadyResponse> {
  const response = await fetch('/ready');
  return response.json();
}
