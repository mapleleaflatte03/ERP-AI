import { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import ErrorBoundary from './components/ErrorBoundary';
import Layout from './components/Layout';

// Main accounting app pages
const DocumentsInbox = lazy(() => import('./pages/DocumentsInbox'));
const DocumentDetail = lazy(() => import('./pages/DocumentDetail'));
const JournalProposal = lazy(() => import('./pages/JournalProposal'));
const ProposalsInbox = lazy(() => import('./pages/ProposalsInbox'));
const ApprovalsInbox = lazy(() => import('./pages/ApprovalsInbox'));
const Reconciliation = lazy(() => import('./pages/Reconciliation'));
const CopilotChat = lazy(() => import('./pages/CopilotChat'));
const Reports = lazy(() => import('./pages/Reports'));
const Evidence = lazy(() => import('./pages/Evidence'));
const DataAnalyst = lazy(() => import('./pages/DataAnalyst'));
const Analytics = lazy(() => import('./pages/Analytics'));

// Admin pages (hidden)
const Testbench = lazy(() => import('./pages/Testbench'));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000,
      retry: 1,
    },
  },
});

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Suspense fallback={<div className="p-6 text-sm text-gray-500">Đang tải...</div>}>
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
                
                {/* Copilot Chat */}
                <Route path="copilot" element={<CopilotChat />} />
                
                {/* Reports */}
                <Route path="reports" element={<Reports />} />
                
                {/* Unified Analyze Module */}
                <Route path="analyze" element={<Analytics />} />
                
                {/* Data Analyst (P2) - Legacy, redirect to Analyze */}
                <Route path="analyst" element={<DataAnalyst />} />
                
                {/* Evidence / Audit Log */}
                <Route path="evidence" element={<Evidence />} />
                <Route path="evidence/:documentId" element={<Evidence />} />
                
                {/* Admin Diagnostics (hidden from main nav) */}
                <Route path="admin/diagnostics" element={<Testbench />} />
                
                {/* Fallback */}
                <Route path="*" element={<Navigate to="/" replace />} />
              </Route>
            </Routes>
          </Suspense>
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
