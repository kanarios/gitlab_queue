import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { getProjects } from '../api/projects';
import type { Project } from '../api/types';

const SELECTED_PROJECT_KEY = 'gitlab-queue.selected-project-id';

interface ProjectContextValue {
  projects: Project[];
  selectedProject: Project | null;
  selectedProjectId: number | null;
  isLoading: boolean;
  error: string | null;
  selectProject: (projectId: number) => void;
  retry: () => void;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

function getStoredProjectId(): number | null {
  try {
    const stored = window.localStorage.getItem(SELECTED_PROJECT_KEY);
    if (!stored || !/^\d+$/.test(stored)) return null;
    const parsed = Number(stored);
    return Number.isSafeInteger(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function storeProjectId(projectId: number | null): void {
  try {
    if (projectId === null) {
      window.localStorage.removeItem(SELECTED_PROJECT_KEY);
    } else {
      window.localStorage.setItem(SELECTED_PROJECT_KEY, String(projectId));
    }
  } catch {
    // The project picker still works for this session if storage is unavailable.
  }
}

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    async function loadProjects() {
      setIsLoading(true);
      setError(null);
      const result = await getProjects(controller.signal);

      if (controller.signal.aborted) return;
      if (!result.success) {
        setProjects([]);
        setError(result.error.message);
        setIsLoading(false);
        return;
      }

      const availableProjects = result.data.projects;
      const storedProjectId = getStoredProjectId();
      const storedProjectIsAvailable = availableProjects.some(
        (project) => project.project_id === storedProjectId
      );
      const nextProjectId = storedProjectIsAvailable
        ? storedProjectId
        : (availableProjects[0]?.project_id ?? null);

      setProjects(availableProjects);
      setSelectedProjectId(nextProjectId);
      storeProjectId(nextProjectId);
      setIsLoading(false);
    }

    void loadProjects();
    return () => controller.abort();
  }, [reloadKey]);

  const selectProject = useCallback(
    (projectId: number) => {
      if (!projects.some((project) => project.project_id === projectId)) return;
      setSelectedProjectId(projectId);
      storeProjectId(projectId);
    },
    [projects]
  );

  const retry = useCallback(() => setReloadKey((key) => key + 1), []);
  const selectedProject = projects.find(
    (project) => project.project_id === selectedProjectId
  ) ?? null;

  const value = useMemo(
    () => ({
      projects,
      selectedProject,
      selectedProjectId,
      isLoading,
      error,
      selectProject,
      retry,
    }),
    [projects, selectedProject, selectedProjectId, isLoading, error, selectProject, retry]
  );

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

export function useProject(): ProjectContextValue {
  const context = useContext(ProjectContext);
  if (!context) {
    throw new Error('useProject must be used within a ProjectProvider');
  }
  return context;
}
