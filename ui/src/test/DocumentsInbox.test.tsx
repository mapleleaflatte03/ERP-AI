import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import DocumentsInbox from '../pages/DocumentsInbox';

// Mock the api module
vi.mock('../lib/api', () => ({
  default: {
    getDocuments: vi.fn().mockResolvedValue([]),
    uploadDocument: vi.fn(),
    isAuthenticated: vi.fn().mockReturnValue(true),
  },
}));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
  },
});

function renderWithProviders(ui: React.ReactElement) {
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{ui}</BrowserRouter>
    </QueryClientProvider>
  );
}

describe('DocumentsInbox', () => {
  it('renders the page with title "Inbox Chứng từ"', () => {
    renderWithProviders(<DocumentsInbox />);
    expect(screen.getByText('Inbox Chứng từ')).toBeInTheDocument();
  });

  it('renders upload area', () => {
    renderWithProviders(<DocumentsInbox />);
    expect(screen.getByText(/Kéo thả chứng từ vào đây/i)).toBeInTheDocument();
  });
});
