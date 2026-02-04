import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  CheckCircle,
  XCircle,
  Clock,
  RefreshCw,
  FileText,
  Eye,
  ThumbsUp,
  Search,
  Filter,
  AlertTriangle,
  TrendingUp,
} from 'lucide-react';
import api from '../lib/api';
import ModuleChatDock from '../components/moduleChat/ModuleChatDock';

interface JournalEntry {
  account_code: string;
  account_name: string;
  debit: number;
  credit: number;
  description: string;
}

interface Proposal {
  id: string;
  document_id: string | null;
  filename: string | null;
  document_type: string | null;
  vendor_name: string | null;
  vendor_tax_id: string | null;
  invoice_number: string | null;
  invoice_date: string | null;
  total_amount: number;
  vat_amount: number;
  currency: string;
  status: string;
  ai_confidence: number;
  ai_reasoning: string | null;
  entries: JournalEntry[];
  total_debit: number;
  total_credit: number;
  is_balanced: boolean;
  created_at: string | null;
}

interface ProposalsResponse {
  proposals: Proposal[];
  total: number;
  limit: number;
  offset: number;
}

function formatCurrency(amount: number | undefined): string {
  if (amount === undefined || amount === null) return '-';
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount);
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleDateString('vi-VN');
}

function getStatusBadge(status: string) {
  switch (status) {
    case 'pending':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
          <Clock className="w-3 h-3" />
          Chờ duyệt
        </span>
      );
    case 'approved':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
          <CheckCircle className="w-3 h-3" />
          Đã duyệt
        </span>
      );
    case 'rejected':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
          <XCircle className="w-3 h-3" />
          Từ chối
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
          {status}
        </span>
      );
  }
}

function getConfidenceBadge(confidence: number) {
  const percent = Math.round(confidence * 100);
  const color = percent >= 80 ? 'green' : percent >= 60 ? 'yellow' : 'red';
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-${color}-100 text-${color}-800`}>
      <TrendingUp className="w-3 h-3" />
      {percent}%
    </span>
  );
}

export default function ProposalsInbox() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null);
  const [statusFilter, setStatusFilter] = useState<'pending' | 'approved' | 'rejected' | ''>('');
  const [searchQuery, setSearchQuery] = useState('');

  // Fetch proposals
  const { data, isLoading, refetch } = useQuery<ProposalsResponse>({
    queryKey: ['journal-proposals', statusFilter],
    queryFn: () => api.getJournalProposals(statusFilter || undefined),
  });

  const proposals = data?.proposals || [];

  // Submit proposal mutation
  const submitMutation = useMutation({
    mutationFn: ({ documentId, proposalId }: { documentId: string; proposalId: string }) =>
      api.submitApproval(documentId, proposalId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['journal-proposals'] });
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      setSelectedProposal(null);
    },
  });

  const handleSubmitForApproval = (proposal: Proposal) => {
    if (!proposal.document_id) {
      alert('Không tìm thấy document_id');
      return;
    }
    if (window.confirm('Gửi đề xuất này để duyệt?')) {
      submitMutation.mutate({
        documentId: proposal.document_id,
        proposalId: proposal.id,
      });
    }
  };

  const filteredProposals = proposals.filter((proposal: Proposal) => {
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        proposal.filename?.toLowerCase().includes(q) ||
        proposal.vendor_name?.toLowerCase().includes(q) ||
        proposal.invoice_number?.toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Quantum Header */}
      <div className="flex items-center justify-between">
        <div className="quantum-header">
          <div className="quantum-header__icon" style={{ background: 'linear-gradient(135deg, #10b981, #34d399)' }}>
            <FileText className="w-7 h-7" />
          </div>
          <div>
            <h1 className="quantum-header__title">Đề xuất hạch toán</h1>
            <p className="quantum-header__subtitle">Xem và quản lý các đề xuất bút toán từ AI</p>
          </div>
        </div>
        <button
          onClick={() => refetch()}
          className="quantum-btn quantum-btn--secondary"
        >
          <RefreshCw className="w-4 h-4" />
          Làm mới
        </button>
      </div>

      {/* Quantum Filters */}
      <div className="flex flex-wrap gap-4">
        <div className="flex-1 min-w-[200px]">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Tìm theo tên file, NCC, số HĐ..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-400 transition-all"
            />
          </div>
        </div>
        <div className="quantum-tabs">
          {[
            { value: '', label: 'Tất cả', icon: Filter },
            { value: 'pending', label: 'Chờ duyệt', icon: Clock },
            { value: 'approved', label: 'Đã duyệt', icon: CheckCircle },
            { value: 'rejected', label: 'Từ chối', icon: XCircle },
          ].map(filter => (
            <button
              key={filter.value}
              onClick={() => setStatusFilter(filter.value as typeof statusFilter)}
              className={`quantum-tab ${statusFilter === filter.value ? 'quantum-tab--active' : ''}`}
            >
              <filter.icon className="w-4 h-4" />
              {filter.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Proposals List */}
        <div className="lg:col-span-1 bg-white rounded-xl border shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b bg-gray-50">
            <h2 className="font-semibold text-gray-900">Danh sách ({filteredProposals.length})</h2>
          </div>
          <div className="divide-y max-h-[600px] overflow-y-auto">
            {isLoading ? (
              <div className="p-4 text-center text-gray-500">
                <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2" />
                Đang tải...
              </div>
            ) : filteredProposals.length === 0 ? (
              <div className="p-8 text-center text-gray-500">
                <FileText className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                <p>Không tìm thấy đề xuất nào</p>
              </div>
            ) : (
              filteredProposals.map((proposal: Proposal) => (
                <div
                  key={proposal.id}
                  onClick={() => setSelectedProposal(proposal)}
                  className={`p-4 cursor-pointer hover:bg-gray-50 transition-colors ${
                    selectedProposal?.id === proposal.id ? 'bg-blue-50 border-l-4 border-l-blue-500' : ''
                  }`}
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <span className="font-medium text-gray-900 truncate text-sm">
                      {proposal.vendor_name || proposal.filename || 'Chưa có tên'}
                    </span>
                    {getStatusBadge(proposal.status)}
                  </div>
                  <div className="text-xs text-gray-500 space-y-1">
                    {proposal.invoice_number && (
                      <div>Số HĐ: {proposal.invoice_number}</div>
                    )}
                    <div className="flex items-center justify-between">
                      <span>{formatDate(proposal.invoice_date)}</span>
                      <span className="font-medium text-gray-700">
                        {formatCurrency(proposal.total_amount)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span>Độ tin cậy: {Math.round((proposal.ai_confidence ?? 0) * 100)}%</span>
                      {proposal.is_balanced === false && (
                        <span className="text-red-500 flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3" />
                          Chưa cân
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Detail Panel */}
        <div className="lg:col-span-2 bg-white rounded-xl border shadow-sm overflow-hidden">
          {selectedProposal ? (
            <div>
              {/* Header */}
              <div className="px-6 py-4 border-b bg-gray-50">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-semibold text-gray-900">
                      {selectedProposal.vendor_name || selectedProposal.filename || 'Chi tiết đề xuất'}
                    </h2>
                    <p className="text-sm text-gray-500 mt-1">
                      {selectedProposal.invoice_number && `Số HĐ: ${selectedProposal.invoice_number}`}
                      {selectedProposal.invoice_date && ` • ${formatDate(selectedProposal.invoice_date)}`}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {getStatusBadge(selectedProposal.status)}
                    {getConfidenceBadge(selectedProposal.ai_confidence)}
                  </div>
                </div>
              </div>

              {/* Content */}
              <div className="p-6 space-y-6">
                {/* Summary Cards */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="bg-gray-50 rounded-lg p-3">
                    <div className="text-xs text-gray-500 mb-1">Tổng tiền HĐ</div>
                    <div className="font-semibold text-gray-900">{formatCurrency(selectedProposal.total_amount)}</div>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <div className="text-xs text-gray-500 mb-1">VAT</div>
                    <div className="font-semibold text-gray-900">{formatCurrency(selectedProposal.vat_amount)}</div>
                  </div>
                  <div className="bg-green-50 rounded-lg p-3">
                    <div className="text-xs text-gray-500 mb-1">Tổng Nợ</div>
                    <div className="font-semibold text-green-700">{formatCurrency(selectedProposal.total_debit)}</div>
                  </div>
                  <div className="bg-blue-50 rounded-lg p-3">
                    <div className="text-xs text-gray-500 mb-1">Tổng Có</div>
                    <div className="font-semibold text-blue-700">{formatCurrency(selectedProposal.total_credit)}</div>
                  </div>
                </div>

                {/* Balance Warning */}
                {!selectedProposal.is_balanced && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center gap-2 text-red-700">
                    <AlertTriangle className="w-5 h-5" />
                    <span className="text-sm">Bút toán chưa cân: Nợ - Có = {formatCurrency(selectedProposal.total_debit - selectedProposal.total_credit)}</span>
                  </div>
                )}

                {/* AI Reasoning */}
                {selectedProposal.ai_reasoning && (
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                    <h3 className="font-medium text-blue-900 mb-2 flex items-center gap-2">
                      <TrendingUp className="w-4 h-4" />
                      Phân tích AI
                    </h3>
                    <p className="text-sm text-blue-800">{selectedProposal.ai_reasoning}</p>
                  </div>
                )}

                {/* Journal Entries */}
                <div>
                  <h3 className="font-medium text-gray-900 mb-3">Bút toán đề xuất</h3>
                  <div className="border rounded-lg overflow-hidden">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-3 text-left font-medium text-gray-600">Tài khoản</th>
                          <th className="px-4 py-3 text-left font-medium text-gray-600">Diễn giải</th>
                          <th className="px-4 py-3 text-right font-medium text-gray-600">Nợ</th>
                          <th className="px-4 py-3 text-right font-medium text-gray-600">Có</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {(selectedProposal.entries?.length ?? 0) > 0 ? (
                          (selectedProposal.entries || []).map((entry, idx) => (
                            <tr key={idx} className="hover:bg-gray-50">
                              <td className="px-4 py-3">
                                <div className="font-medium">{entry.account_code}</div>
                                <div className="text-xs text-gray-500">{entry.account_name}</div>
                              </td>
                              <td className="px-4 py-3 text-gray-600">{entry.description || '-'}</td>
                              <td className="px-4 py-3 text-right font-medium text-green-600">
                                {entry.debit > 0 ? formatCurrency(entry.debit) : '-'}
                              </td>
                              <td className="px-4 py-3 text-right font-medium text-blue-600">
                                {entry.credit > 0 ? formatCurrency(entry.credit) : '-'}
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={4} className="px-4 py-8 text-center text-gray-500">
                              Chưa có bút toán chi tiết
                            </td>
                          </tr>
                        )}
                      </tbody>
                      <tfoot className="bg-gray-50 font-semibold">
                        <tr>
                          <td colSpan={2} className="px-4 py-3 text-right">Tổng cộng</td>
                          <td className="px-4 py-3 text-right text-green-700">{formatCurrency(selectedProposal.total_debit)}</td>
                          <td className="px-4 py-3 text-right text-blue-700">{formatCurrency(selectedProposal.total_credit)}</td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center justify-between pt-4 border-t">
                  <div className="flex gap-2">
                    {selectedProposal.document_id && (
                      <button
                        onClick={() => navigate(`/documents/${selectedProposal.document_id}`)}
                        className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
                      >
                        <Eye className="w-4 h-4" />
                        Xem chứng từ
                      </button>
                    )}
                  </div>
                  {selectedProposal.status === 'pending' && selectedProposal.document_id && (
                    <button
                      onClick={() => handleSubmitForApproval(selectedProposal)}
                      disabled={submitMutation.isPending}
                      className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                    >
                      <ThumbsUp className="w-4 h-4" />
                      {submitMutation.isPending ? 'Đang gửi...' : 'Gửi duyệt'}
                    </button>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-96 text-gray-500">
              <FileText className="w-16 h-16 text-gray-300 mb-4" />
              <p>Chọn một đề xuất để xem chi tiết</p>
            </div>
          )}
        </div>
      </div>
      <ModuleChatDock module="proposals" />
    </div>
  );
}
