import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';
import Testbench from './pages/Testbench';
import UploadRun from './pages/UploadRun';
import JobsInspector from './pages/JobsInspector';
import Approvals from './pages/Approvals';
import Observability from './pages/Observability';

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
            <Route index element={<Testbench />} />
            <Route path="upload" element={<UploadRun />} />
            <Route path="jobs" element={<JobsInspector />} />
            <Route path="approvals" element={<Approvals />} />
            <Route path="observability" element={<Observability />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
