import { useState, useEffect, useCallback } from 'react';
import { getReadyStatus, ReadyResponse } from '../api/health';
import { config } from '../config';

/** Health check hook return type. */
export interface UseHealthCheckResult {
  /** Full health response from backend. */
  health: ReadyResponse | null;
  /** Whether the initial health check is loading. */
  isLoading: boolean;
  /** Error if health check failed. */
  error: Error | null;
  /** Whether the backend is ready (shorthand for health.ready). */
  isHealthy: boolean;
  /** Application mode: normal, degraded, or unhealthy. */
  mode: 'normal' | 'degraded' | 'unhealthy' | 'unknown';
  /** Manually trigger a health check. */
  refetch: () => Promise<void>;
}

/**
 * Hook for periodic health monitoring.
 *
 * Fetches health status on mount and then periodically based on
 * config.healthCheckInterval.
 */
export function useHealthCheck(): UseHealthCheckResult {
  const [health, setHealth] = useState<ReadyResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchHealth = useCallback(async () => {
    try {
      const data = await getReadyStatus();
      setHealth(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Health check failed'));
      setHealth(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, config.healthCheckInterval);
    return () => clearInterval(interval);
  }, [fetchHealth]);

  return {
    health,
    isLoading,
    error,
    isHealthy: health?.ready ?? false,
    mode: health?.mode ?? 'unknown',
    refetch: fetchHealth,
  };
}
