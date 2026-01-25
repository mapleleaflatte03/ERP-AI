import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import CopilotChat from '../pages/CopilotChat';

// Mock the api module
vi.mock('../lib/api', () => ({
  default: {
    sendCopilotMessage: vi.fn().mockResolvedValue({ message: 'Test response' }),
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

describe('CopilotChat', () => {
  it('renders the chat page with title "Trợ lý AI Kế toán"', () => {
    renderWithProviders(<CopilotChat />);
    expect(screen.getByText('Trợ lý AI Kế toán')).toBeInTheDocument();
  });

  it('renders suggested questions', () => {
    renderWithProviders(<CopilotChat />);
    expect(screen.getByText(/Giải thích định khoản mua hàng/i)).toBeInTheDocument();
  });

  it('renders chat input placeholder', () => {
    renderWithProviders(<CopilotChat />);
    expect(screen.getByPlaceholderText(/Hỏi về nghiệp vụ kế toán/i)).toBeInTheDocument();
  });
});
