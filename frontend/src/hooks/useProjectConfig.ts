import { useEffect, useState } from 'react';
import { getProjectConfig } from '../api/config';
import { useProject } from '../projects/ProjectContext';

export function useProjectConfig(): { projectWebUrl: string | null } {
  const { selectedProject } = useProject();
  const [projectWebUrl, setProjectWebUrl] = useState<string | null>(
    selectedProject?.web_url || null
  );

  useEffect(() => {
    const projectId = selectedProject?.project_id;
    const listedUrl = selectedProject?.web_url || null;
    setProjectWebUrl(listedUrl);
    if (!projectId || listedUrl) return;

    const controller = new AbortController();
    let retryTimeout: ReturnType<typeof setTimeout> | null = null;

    const loadConfig = async () => {
      const result = await getProjectConfig(projectId, controller.signal);
      if (controller.signal.aborted) return;
      if (result.success) {
        setProjectWebUrl(result.data.project_web_url);
      } else {
        retryTimeout = setTimeout(() => void loadConfig(), 30_000);
      }
    };

    void loadConfig();
    return () => {
      controller.abort();
      if (retryTimeout) clearTimeout(retryTimeout);
    };
  }, [selectedProject]);

  return { projectWebUrl };
}
