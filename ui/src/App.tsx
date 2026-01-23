import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';

// Main accounting app pages
import DocumentsInbox from './pages/DocumentsInbox';
import DocumentDetail from './pages/DocumentDetail';
import JournalProposal from './pages/JournalProposal';
import ApprovalsInbox from './pages/ApprovalsInbox';
import Reconciliation from './pages/Reconciliation';
import CopilotChat from './pages/CopilotChat';
import Reports from './pages/Reports';
import Evidence from './pages/Evidence';

// Admin pages (hidden)
import Testbench from './pages/Testbench';

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
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            {/* Main accounting workflow */}
            <Route index element={<DocumentsInbox />} />
            <Route path="documents/:id" element={<DocumentDetail />} />
            <Route path="documents/:id/proposal" element={<JournalProposal />} />
            
            {/* Proposals list - reuses JournalProposal with empty doc context */}
            <Route path="proposals" element={<JournalProposal />} />
            
            {/* Approvals */}
            <Route path="approvals" element={<ApprovalsInbox />} />
            
            {/* Reconciliation */}
            <Route path="reconciliation" element={<Reconciliation />} />
            
            {/* Copilot Chat */}
            <Route path="copilot" element={<CopilotChat />} />
            
            {/* Reports */}
            <Route path="reports" element={<Reports />} />
            
            {/* Evidence / Audit Log */}
            <Route path="evidence" element={<Evidence />} />
            <Route path="evidence/:documentId" element={<Evidence />} />
            
            {/* Admin Diagnostics (hidden from main nav) */}
            <Route path="admin/diagnostics" element={<Testbench />} />
            
            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
