import { describe, expect, it, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { ProjectProvider, useProject } from '../../projects/ProjectContext';
import { server } from '../mocks/server';

function ProjectProbe() {
  const { projects, selectedProject, selectProject, isLoading, retry } = useProject();

  return (
    <div>
      <p role="status">{isLoading ? 'Loading projects' : `Loaded ${projects.length}`}</p>
      <p>Selected: {selectedProject?.name ?? 'none'}</p>
      <button type="button" onClick={() => selectProject(2)}>Choose second</button>
      <button type="button" onClick={retry}>Try again</button>
    </div>
  );
}

function renderProjectProbe() {
  return render(
    <ProjectProvider>
      <ProjectProbe />
    </ProjectProvider>
  );
}

describe('ProjectContext', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('loads the available projects and selects the first project by default', async () => {
    renderProjectProbe();

    expect(screen.getByRole('status')).toHaveTextContent('Loading projects');
    expect(await screen.findByText('Loaded 2')).toBeInTheDocument();
    expect(screen.getByText('Selected: group/project')).toBeInTheDocument();
  });

  it('persists a user selection and restores it when it is still available', async () => {
    localStorage.setItem('gitlab-queue.selected-project-id', '2');
    renderProjectProbe();

    expect(await screen.findByText('Selected: group/second')).toBeInTheDocument();
  });

  it('keeps the stored selection after a transient load error and restores it on retry', async () => {
    localStorage.setItem('gitlab-queue.selected-project-id', '2');
    let attempts = 0;
    server.use(
      http.get('/api/projects', () => {
        attempts += 1;
        if (attempts === 1) {
          return HttpResponse.json({ detail: 'Temporary error' }, { status: 503 });
        }
        return HttpResponse.json({
          projects: [
            { project_id: 1, web_url: 'https://gitlab.example.com/group/project', name: 'group/project' },
            { project_id: 2, web_url: 'https://gitlab.example.com/group/second', name: 'group/second' },
          ],
        });
      })
    );

    renderProjectProbe();

    expect(await screen.findByText('Loaded 0')).toBeInTheDocument();
    expect(screen.getByText('Selected: none')).toBeInTheDocument();
    expect(localStorage.getItem('gitlab-queue.selected-project-id')).toBe('2');

    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));

    expect(await screen.findByText('Loaded 2')).toBeInTheDocument();
    expect(screen.getByText('Selected: group/second')).toBeInTheDocument();
    expect(localStorage.getItem('gitlab-queue.selected-project-id')).toBe('2');
  });

  it('changes to the chosen project and persists the selection', async () => {
    renderProjectProbe();

    expect(await screen.findByText('Selected: group/project')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Choose second' }));
    expect(await screen.findByText('Selected: group/second')).toBeInTheDocument();
    await waitFor(() => expect(localStorage.getItem('gitlab-queue.selected-project-id')).toBe('2'));
  });

  it('does not restore a stored project id that is absent from the API list', async () => {
    localStorage.setItem('gitlab-queue.selected-project-id', '999');
    renderProjectProbe();

    expect(await screen.findByText('Selected: group/project')).toBeInTheDocument();
    await waitFor(() => expect(localStorage.getItem('gitlab-queue.selected-project-id')).toBe('1'));
  });

  it('reports an empty API project list without restoring the stored id', async () => {
    localStorage.setItem('gitlab-queue.selected-project-id', '2');
    server.use(
      http.get('/api/projects', () => HttpResponse.json({ projects: [] }))
    );

    renderProjectProbe();

    expect(await screen.findByText('Loaded 0')).toBeInTheDocument();
    expect(screen.getByText('Selected: none')).toBeInTheDocument();
    expect(localStorage.getItem('gitlab-queue.selected-project-id')).toBeNull();
  });
});
