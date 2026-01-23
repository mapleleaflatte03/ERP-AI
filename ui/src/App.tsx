import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Jobs from './pages/Jobs';
import Approvals from './pages/Approvals';
import Forecasts from './pages/Forecasts';
import Simulations from './pages/Simulations';
import Insights from './pages/Insights';
import Evidence from './pages/Evidence';

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
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="jobs" element={<Jobs />} />
            <Route path="approvals" element={<Approvals />} />
            <Route path="forecasts" element={<Forecasts />} />
            <Route path="simulations" element={<Simulations />} />
            <Route path="insights" element={<Insights />} />
            <Route path="evidence" element={<Evidence />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
