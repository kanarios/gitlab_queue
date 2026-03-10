/**
 * Tests for hooks/useProjectConfig.ts - Project config hook with retry logic.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import { useProjectConfig } from '../../hooks/useProjectConfig';

const mockConfigResponse = {
  project_web_url: 'https://gitlab.example.com/group/project',
};

describe('hooks/useProjectConfig', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    server.use(
      http.get('/api/config', () => {
        return HttpResponse.json(mockConfigResponse);
      })
    );
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('starts with null projectWebUrl', () => {
    const { result } = renderHook(() => useProjectConfig());

    expect(result.current.projectWebUrl).toBeNull();
  });

  it('sets projectWebUrl on successful fetch', async () => {
    const { result } = renderHook(() => useProjectConfig());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(result.current.projectWebUrl).toBe(
      'https://gitlab.example.com/group/project'
    );
  });

  it('retries on failure and succeeds on second attempt', async () => {
    let callCount = 0;
    server.use(
      http.get('/api/config', () => {
        callCount++;
        if (callCount === 1) {
          return HttpResponse.json(
            { detail: 'Server error' },
            { status: 500 }
          );
        }
        return HttpResponse.json(mockConfigResponse);
      })
    );

    const { result } = renderHook(() => useProjectConfig());

    // First attempt fails — wait for it to complete
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.projectWebUrl).toBeNull();

    // Advance past first retry delay (5000ms)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    expect(result.current.projectWebUrl).toBe(
      'https://gitlab.example.com/group/project'
    );
  });

  it('stays null when all retries are exhausted', async () => {
    server.use(
      http.get('/api/config', () => {
        return HttpResponse.json(
          { detail: 'Server error' },
          { status: 500 }
        );
      })
    );

    const { result } = renderHook(() => useProjectConfig());

    // Initial attempt + 4 retries with delays [5000, 15000, 30000, 60000]
    const delays = [0, 5000, 15000, 30000, 60000];
    for (const delay of delays) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(delay);
      });
    }

    expect(result.current.projectWebUrl).toBeNull();
  });

  it('stops retrying on unmount', async () => {
    let callCount = 0;
    server.use(
      http.get('/api/config', () => {
        callCount++;
        return HttpResponse.json(
          { detail: 'Server error' },
          { status: 500 }
        );
      })
    );

    const { unmount } = renderHook(() => useProjectConfig());

    // Wait for first attempt
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    const callsBeforeUnmount = callCount;
    unmount();

    // Advance past all retry delays
    await act(async () => {
      await vi.advanceTimersByTimeAsync(120000);
    });

    // No additional calls after unmount
    expect(callCount).toBe(callsBeforeUnmount);
  });

  it('clears pending timeout on unmount during retry delay', async () => {
    server.use(
      http.get('/api/config', () => {
        return HttpResponse.json(
          { detail: 'Server error' },
          { status: 500 }
        );
      })
    );

    const clearTimeoutSpy = vi.spyOn(globalThis, 'clearTimeout');

    const { unmount } = renderHook(() => useProjectConfig());

    // Wait for first attempt to fail
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    // Partially advance into first retry delay (timeout is pending)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    unmount();

    expect(clearTimeoutSpy).toHaveBeenCalled();
  });
});
