import { useState, useEffect } from 'react';
import { getProjectConfig } from '../api/config';

const RETRY_DELAYS = [5000, 15000, 30000, 60000];

export function useProjectConfig(): { projectWebUrl: string | null } {
  const [projectWebUrl, setProjectWebUrl] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    async function fetchWithRetries() {
      for (let attempt = 0; attempt <= RETRY_DELAYS.length; attempt++) {
        const result = await getProjectConfig(controller.signal);
        if (result.success) {
          setProjectWebUrl(result.data.project_web_url);
          return;
        }
        if (controller.signal.aborted) return;
        if (attempt >= RETRY_DELAYS.length) return;

        await new Promise<void>((resolve) => {
          timeoutId = setTimeout(resolve, RETRY_DELAYS[attempt]);
        });
        if (controller.signal.aborted) return;
      }
    }

    fetchWithRetries();

    return () => {
      controller.abort();
      if (timeoutId !== null) {
        clearTimeout(timeoutId);
      }
    };
  }, []);

  return { projectWebUrl };
}
