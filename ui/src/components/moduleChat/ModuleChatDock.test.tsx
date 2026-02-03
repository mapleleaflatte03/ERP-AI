/**
 * Tests for ModuleChatDock component
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Mock the API module
vi.mock('../../lib/api', () => ({
  default: {
    post: vi.fn(),
  },
}));

// Mock ActionProposalCard
vi.mock('../ActionProposalCard', () => ({
  default: ({ proposal, onStatusChange }: any) => (
    <div data-testid="action-proposal-card">
      <span>{proposal.description}</span>
      <button onClick={() => onStatusChange?.('executed')}>Confirm</button>
    </div>
  ),
}));

import ModuleChatDock from './ModuleChatDock';
import api from '../../lib/api';

describe('ModuleChatDock', () => {
  beforeEach(() => {
    // Clear localStorage
    localStorage.clear();
    // Reset mocks
    vi.clearAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('Initial Render', () => {
    it('should render dock button when closed', () => {
      render(<ModuleChatDock module="documents" />);
      
      // Should show the floating button
      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
      expect(button).toHaveAttribute('title', 'Mở Tài liệu AI');
    });

    it('should show correct icon for each module', () => {
      const { rerender } = render(<ModuleChatDock module="documents" />);
      expect(screen.getByText('📄')).toBeInTheDocument();

      rerender(<ModuleChatDock module="approvals" />);
      expect(screen.getByText('✅')).toBeInTheDocument();

      rerender(<ModuleChatDock module="proposals" />);
      expect(screen.getByText('📋')).toBeInTheDocument();

      rerender(<ModuleChatDock module="analyze" />);
      expect(screen.getByText('📊')).toBeInTheDocument();
    });
  });

  describe('Open/Close Behavior', () => {
    it('should open chat panel when dock button clicked', async () => {
      render(<ModuleChatDock module="documents" />);
      
      const button = screen.getByRole('button');
      await userEvent.click(button);
      
      // Should show the chat panel with header
      expect(screen.getByText('Tài liệu AI')).toBeInTheDocument();
    });

    it('should close when X button clicked', async () => {
      render(<ModuleChatDock module="documents" />);
      
      // Open the chat
      await userEvent.click(screen.getByRole('button'));
      expect(screen.getByText('Tài liệu AI')).toBeInTheDocument();
      
      // Click close
      const closeButton = screen.getByTitle('Đóng');
      await userEvent.click(closeButton);
      
      // Should show dock button again
      await waitFor(() => {
        expect(screen.queryByText('Tài liệu AI')).not.toBeInTheDocument();
      });
    });

    it('should call onClose callback when closed', async () => {
      const onClose = vi.fn();
      render(<ModuleChatDock module="documents" onClose={onClose} />);
      
      // Open then close
      await userEvent.click(screen.getByRole('button'));
      await userEvent.click(screen.getByTitle('Đóng'));
      
      expect(onClose).toHaveBeenCalled();
    });
  });

  describe('LocalStorage Persistence', () => {
    it('should persist open state to localStorage', async () => {
      render(<ModuleChatDock module="documents" />);
      
      // Open the chat
      await userEvent.click(screen.getByRole('button'));
      
      // Check localStorage
      const stored = JSON.parse(localStorage.getItem('erpx_chat_state') || '{}');
      expect(stored.documents.isOpen).toBe(true);
    });

    it('should restore state from localStorage', () => {
      // Set initial state
      localStorage.setItem('erpx_chat_state', JSON.stringify({
        documents: { isOpen: true, isMinimized: false, isExpanded: false }
      }));
      
      render(<ModuleChatDock module="documents" />);
      
      // Should be open
      expect(screen.getByText('Tài liệu AI')).toBeInTheDocument();
    });
  });

  describe('Minimize/Expand', () => {
    it('should minimize when minimize button clicked', async () => {
      render(<ModuleChatDock module="documents" />);
      
      // Open the chat
      await userEvent.click(screen.getByRole('button'));
      
      // Minimize
      await userEvent.click(screen.getByTitle('Thu nhỏ'));
      
      // Should show minimized state (title but not input)
      expect(screen.queryByPlaceholderText(/Hỏi về/)).not.toBeInTheDocument();
    });

    it('should expand when expand button clicked', async () => {
      render(<ModuleChatDock module="documents" />);
      
      // Open the chat
      await userEvent.click(screen.getByRole('button'));
      
      // Get current width/height from style
      const panel = screen.getByText('Tài liệu AI').closest('div')?.parentElement;
      const initialWidth = panel?.style.width;
      
      // Expand
      await userEvent.click(screen.getByTitle('Mở rộng'));
      
      // Should have larger dimensions
      const expandedWidth = panel?.style.width;
      expect(expandedWidth).not.toBe(initialWidth);
    });
  });

  describe('Sending Messages', () => {
    it('should send message on Enter key', async () => {
      (api.post as any).mockResolvedValue({
        data: {
          response: 'Test response',
          proposed_actions: [],
        }
      });

      render(<ModuleChatDock module="documents" />);
      
      // Open the chat
      await userEvent.click(screen.getByRole('button'));
      
      // Type and send
      const input = screen.getByPlaceholderText(/Hỏi về tài liệu/);
      await userEvent.type(input, 'Test message{enter}');
      
      // Should call API
      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith(
          '/v1/chat/documents',
          expect.objectContaining({ message: 'Test message' })
        );
      });
    });

    it('should display user message immediately', async () => {
      (api.post as any).mockResolvedValue({
        data: { response: 'Response', proposed_actions: [] }
      });

      render(<ModuleChatDock module="documents" />);
      await userEvent.click(screen.getByRole('button'));
      
      const input = screen.getByPlaceholderText(/Hỏi về tài liệu/);
      await userEvent.type(input, 'Hello AI{enter}');
      
      // User message should appear
      expect(screen.getByText('Hello AI')).toBeInTheDocument();
    });

    it('should display assistant response', async () => {
      (api.post as any).mockResolvedValue({
        data: { response: 'AI response here', proposed_actions: [] }
      });

      render(<ModuleChatDock module="documents" />);
      await userEvent.click(screen.getByRole('button'));
      
      const input = screen.getByPlaceholderText(/Hỏi về tài liệu/);
      await userEvent.type(input, 'Test{enter}');
      
      await waitFor(() => {
        expect(screen.getByText('AI response here')).toBeInTheDocument();
      });
    });

    it('should show loading state while waiting', async () => {
      // Delay the response
      (api.post as any).mockImplementation(() => 
        new Promise(resolve => setTimeout(() => resolve({
          data: { response: 'Done', proposed_actions: [] }
        }), 100))
      );

      render(<ModuleChatDock module="documents" />);
      await userEvent.click(screen.getByRole('button'));
      
      const input = screen.getByPlaceholderText(/Hỏi về tài liệu/);
      await userEvent.type(input, 'Test{enter}');
      
      // Should show loading indicator
      expect(screen.getByText('Đang suy nghĩ...')).toBeInTheDocument();
      
      // Wait for response
      await waitFor(() => {
        expect(screen.queryByText('Đang suy nghĩ...')).not.toBeInTheDocument();
      });
    });
  });

  describe('Action Proposals', () => {
    it('should render action proposals from response', async () => {
      (api.post as any).mockResolvedValue({
        data: {
          response: 'Here is an action',
          proposed_actions: [{
            proposal_id: 'test-123',
            action_type: 'approve_proposal',
            description: 'Approve document',
            risk_level: 'medium',
            confirm_url: '/v1/agent/actions/test-123/confirm',
          }]
        }
      });

      render(<ModuleChatDock module="approvals" />);
      await userEvent.click(screen.getByRole('button'));
      
      const input = screen.getByPlaceholderText(/Hỏi về duyệt/);
      await userEvent.type(input, 'Approve{enter}');
      
      await waitFor(() => {
        expect(screen.getByTestId('action-proposal-card')).toBeInTheDocument();
        expect(screen.getByText('Approve document')).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('should display error message on API failure', async () => {
      (api.post as any).mockRejectedValue(new Error('Network error'));

      render(<ModuleChatDock module="documents" />);
      await userEvent.click(screen.getByRole('button'));
      
      const input = screen.getByPlaceholderText(/Hỏi về tài liệu/);
      await userEvent.type(input, 'Test{enter}');
      
      await waitFor(() => {
        expect(screen.getByText(/Lỗi/)).toBeInTheDocument();
      });
    });
  });

  describe('Scope ID', () => {
    it('should include scope_id in API requests', async () => {
      (api.post as any).mockResolvedValue({
        data: { response: 'Response', proposed_actions: [] }
      });

      render(<ModuleChatDock module="documents" scopeId="doc-abc-123" />);
      await userEvent.click(screen.getByRole('button'));
      
      const input = screen.getByPlaceholderText(/Hỏi về tài liệu/);
      await userEvent.type(input, 'Test{enter}');
      
      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith(
          '/v1/chat/documents',
          expect.objectContaining({ scope_id: 'doc-abc-123' })
        );
      });
    });

    it('should show truncated scope_id in header', async () => {
      render(<ModuleChatDock module="documents" scopeId="document-12345678-abcd" />);
      await userEvent.click(screen.getByRole('button'));
      
      // Should show truncated ID
      expect(screen.getByText(/document-/)).toBeInTheDocument();
    });
  });
});
