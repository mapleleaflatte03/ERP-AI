import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import Layout from '../components/Layout';

// Mock the api module
vi.mock('../lib/api', () => ({
  default: {
    isAuthenticated: vi.fn().mockReturnValue(true),
    clearToken: vi.fn(),
  },
}));

describe('Layout - Sidebar Navigation', () => {
  it('renders sidebar with Vietnamese navigation items', () => {
    render(
      <MemoryRouter>
        <Layout />
      </MemoryRouter>
    );
    
    // Check main navigation items exist
    expect(screen.getByText('AI Kế Toán')).toBeInTheDocument();
    expect(screen.getAllByText('Chứng từ').length).toBeGreaterThan(0);
    expect(screen.getByText('Đề xuất hạch toán')).toBeInTheDocument();
    expect(screen.getByText('Duyệt')).toBeInTheDocument();
    expect(screen.getByText('Đối chiếu')).toBeInTheDocument();
    expect(screen.getByText('Trợ lý AI')).toBeInTheDocument();
    expect(screen.getByText('Báo cáo')).toBeInTheDocument();
    expect(screen.getByText('Lịch sử')).toBeInTheDocument();
  });

  it('shows authentication status', () => {
    render(
      <MemoryRouter>
        <Layout />
      </MemoryRouter>
    );
    
    expect(screen.getByText('Đã kết nối')).toBeInTheDocument();
  });
});
