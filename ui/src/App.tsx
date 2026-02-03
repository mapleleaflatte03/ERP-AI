import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { lazy, Suspense, useEffect } from 'react';
import ErrorBoundary from './components/ErrorBoundary';
import Layout from './components/Layout';
import { UIPreferencesProvider } from './contexts/UIPreferencesContext';
import { initWebVitals } from './lib/webVitals';

// Import design tokens
import './styles/tokens.css';

// Main accounting app pages
import DocumentsInbox from './pages/DocumentsInbox';
import DocumentDetail from './pages/DocumentDetail';
import JournalProposal from './pages/JournalProposal';
import ProposalsInbox from './pages/ProposalsInbox';
import ApprovalsInbox from './pages/ApprovalsInbox';
import Reconciliation from './pages/Reconciliation';
import Reports from './pages/Reports';
import Evidence from './pages/Evidence';

// Lazy-loaded heavy pages (code splitting)
const CopilotChat = lazy(() => import('./pages/CopilotChat'));
const Analytics = lazy(() => import('./pages/Analytics'));
const DataAnalyst = lazy(() => import('./pages/DataAnalyst'));
const Testbench = lazy(() => import('./pages/Testbench'));

// Loading fallback
function PageLoader() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="flex items-center gap-3 text-[var(--color-text-secondary)]">
        <div className="w-6 h-6 border-2 border-current border-t-transparent rounded-full animate-spin" />
        <span>Đang tải...</span>
      </div>
    </div>
  );
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000,
      retry: 1,
    },
  },
});

export default function App() {
  // Initialize web vitals tracking
  useEffect(() => {
    initWebVitals();
  }, []);

  return (
    <ErrorBoundary>
      <UIPreferencesProvider>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<Layout />}>
                {/* Main accounting workflow */}
                <Route index element={<DocumentsInbox />} />
                <Route path="documents/:id" element={<DocumentDetail />} />
                <Route path="documents/:id/proposal" element={<JournalProposal />} />
                
                {/* Proposals list */}
                <Route path="proposals" element={<ProposalsInbox />} />
                
                {/* Approvals */}
                <Route path="approvals" element={<ApprovalsInbox />} />
                
                {/* Reconciliation */}
                <Route path="reconciliation" element={<Reconciliation />} />
                
                {/* Copilot Chat (lazy loaded) */}
                <Route path="copilot" element={
                  <Suspense fallback={<PageLoader />}>
                    <CopilotChat />
                  </Suspense>
                } />
                
                {/* Reports */}
                <Route path="reports" element={<Reports />} />
                
                {/* Unified Analyze Module (lazy loaded) */}
                <Route path="analyze" element={
                  <Suspense fallback={<PageLoader />}>
                    <Analytics />
                  </Suspense>
                } />
                
                {/* Data Analyst (P2) - Legacy (lazy loaded) */}
                <Route path="analyst" element={
                  <Suspense fallback={<PageLoader />}>
                    <DataAnalyst />
                  </Suspense>
                } />
                
                {/* Evidence / Audit Log */}
                <Route path="evidence" element={<Evidence />} />
                <Route path="evidence/:documentId" element={<Evidence />} />
                
                {/* Admin Diagnostics (lazy loaded) */}
                <Route path="admin/diagnostics" element={
                  <Suspense fallback={<PageLoader />}>
                    <Testbench />
                  </Suspense>
                } />
                
                {/* Fallback */}
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </QueryClientProvider>
      </UIPreferencesProvider>
    </ErrorBoundary>
  );
}
