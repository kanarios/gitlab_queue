import React, { useState, useEffect } from 'react';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import History from './pages/History';
import Analytics from './pages/Analytics';
import { ViewMode, MergeRequest, MRStatus } from './types';
import { initialQueue, initialHistory } from './mockData';

const App = () => {
  const [view, setView] = useState<ViewMode>('dashboard');
  const [queue, setQueue] = useState<MergeRequest[]>(initialQueue);
  const [history, setHistory] = useState<MergeRequest[]>(initialHistory);
  const [isDark, setIsDark] = useState(true);

  // Theme toggle effect
  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDark]);

  const toggleTheme = () => setIsDark(!isDark);

  // Simulation Logic to make the UI interactive
  const simulateAdvance = () => {
    if (queue.length === 0) return;

    setQueue(prevQueue => {
      const newQueue = [...prevQueue];
      const activeIndex = newQueue.findIndex(mr => [MRStatus.REBASING, MRStatus.TESTING, MRStatus.MERGING].includes(mr.status));

      if (activeIndex !== -1) {
        // Advance current item
        const active = newQueue[activeIndex];
        if (active.status === MRStatus.REBASING) active.status = MRStatus.TESTING;
        else if (active.status === MRStatus.TESTING) active.status = MRStatus.MERGING;
        else if (active.status === MRStatus.MERGING) {
           // Move to history
           const finishedItem = { ...active, status: MRStatus.MERGED, finishedAt: new Date().toISOString() };
           setHistory(prev => [finishedItem, ...prev]);
           newQueue.splice(activeIndex, 1);
           
           // Start next if exists
           if (newQueue.length > 0) {
               newQueue[0].status = MRStatus.REBASING;
               newQueue[0].startedAt = new Date().toISOString();
           }
        }
      } else if (newQueue.length > 0) {
          // No active item, start first
          newQueue[0].status = MRStatus.REBASING;
          newQueue[0].startedAt = new Date().toISOString();
      }
      return newQueue;
    });
  };

  const simulateAdd = () => {
      const newMR: MergeRequest = {
          iid: Math.floor(Math.random() * 1000) + 2000,
          title: "feat: New awesome feature implementation",
          author: { name: "Simulator User", username: "@sim", avatar: "https://picsum.photos/seed/sim/64/64" },
          status: MRStatus.QUEUED,
          labels: ["merge_queue"],
          isHotfix: false,
          queuedAt: new Date().toISOString(),
          targetBranch: "master"
      };
      setQueue(prev => [...prev, newMR]);
  };

  const simulateHotfix = () => {
      const newMR: MergeRequest = {
          iid: Math.floor(Math.random() * 1000) + 9000,
          title: "fix: PRODUCTION OUTAGE FIX",
          author: { name: "Lead Dev", username: "@lead", avatar: "https://picsum.photos/seed/lead/64/64" },
          status: MRStatus.QUEUED,
          labels: ["merge_queue", "hotfix"],
          isHotfix: true,
          queuedAt: new Date().toISOString(),
          targetBranch: "master"
      };
      // Logic: Hotfix goes after active item, or first if none
      setQueue(prev => {
          const activeIndex = prev.findIndex(mr => [MRStatus.REBASING, MRStatus.TESTING, MRStatus.MERGING].includes(mr.status));
          const newQ = [...prev];
          if (activeIndex !== -1) {
              newQ.splice(activeIndex + 1, 0, newMR);
          } else {
              newQ.unshift(newMR);
          }
          return newQ;
      });
  };

  return (
    <Layout currentView={view} setView={setView} isDark={isDark} toggleTheme={toggleTheme}>
      {view === 'dashboard' && (
        <Dashboard 
            queue={queue} 
            onSimulateAdvance={simulateAdvance} 
            onSimulateAdd={simulateAdd}
            onSimulateHotfix={simulateHotfix}
        />
      )}
      {view === 'history' && <History history={history} />}
      {view === 'analytics' && (
          <Analytics stats={{
              totalProcessed: 1248,
              avgWaitTimeMinutes: 24,
              successRate: 94.2,
              activeSince: "2023-10-01"
          }} />
      )}
    </Layout>
  );
};

export default App;