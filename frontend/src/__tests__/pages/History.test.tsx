import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import History from '../../pages/History';
import { ProjectProvider } from '../../projects/ProjectContext';
import { mockHistoryItem } from '../mocks/handlers';
import { server } from '../mocks/server';

describe('History page pagination', () => {
  it('corrects an out-of-range page and loads records from the last available page', async () => {
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      value: vi.fn((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
    const requestedPages: string[] = [];
    server.use(
      http.get('/api/projects/1/history', ({ request }) => {
        const url = new URL(request.url);
        const requestedPage = url.searchParams.get('page') ?? '1';
        requestedPages.push(requestedPage);
        const page = Number(requestedPage);

        return HttpResponse.json({
          items: page === 2
            ? [{ ...mockHistoryItem, mr_iid: 222, title: 'Record on the last page' }]
            : [],
          pagination: {
            page,
            per_page: 20,
            total: 40,
            total_pages: 2,
          },
        });
      })
    );

    render(
      <MemoryRouter initialEntries={['/history?page=9']}>
        <ProjectProvider>
          <Routes>
            <Route path="/history" element={<History projectId={1} />} />
          </Routes>
        </ProjectProvider>
      </MemoryRouter>
    );

    expect(await screen.findByText('Record on the last page')).toBeInTheDocument();
    await waitFor(() => expect(requestedPages).toEqual(['9', '2']));
    expect(screen.getByText('21')).toBeInTheDocument();
    expect(screen.getAllByText('40')).toHaveLength(2);
  });
});
