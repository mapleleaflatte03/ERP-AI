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
  ThumbsDown,
  Search,
  Filter,
  AlertTriangle,
} from 'lucide-react';
import api from '../lib/api';
import type { Approval, JournalEntryLine } from '../types';

function formatCurrency(amount: number | undefined): string {
  if (amount === undefined || amount === null) return '-';
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount);
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString('vi-VN');
}

export default function ApprovalsInbox() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selectedApproval, setSelectedApproval] = useState<Approval | null>(null);
  const [rejectNote, setRejectNote] = useState('');
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [statusFilter, setStatusFilter] = useState<'pending' | 'approved' | 'rejected' | ''>('pending');
  const [searchQuery, setSearchQuery] = useState('');
  // Pagination
  const [page, setPage] = useState(1);
  const [limit] = useState(20);

  // Fetch approvals
  const { data: response, isLoading, refetch } = useQuery({
    queryKey: ['approvals', statusFilter, page, limit],
    queryFn: () => api.getApprovals(statusFilter || undefined, limit, (page - 1) * limit),
  });

  // Handle potential object response { approvals: [], count: ... } or array []
  const approvalsList = Array.isArray(response)
    ? response
    : (response && typeof response === 'object' && 'approvals' in response)
      ? (response.approvals || [])
      : [];

  const totalCount = (response && !Array.isArray(response) && 'count' in response)
    ? response.count
    : approvalsList.length;

  const totalPages = Math.ceil(totalCount / limit);

  // Approve mutation
  const approveMutation = useMutation({
    mutationFn: (approvalId: string) => api.approveDocument(approvalId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      setSelectedApproval(null);
    },
  });

  // Reject mutation
  const rejectMutation = useMutation({
    mutationFn: ({ approvalId, note }: { approvalId: string; note: string }) =>
      api.rejectDocument(approvalId, note),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      setSelectedApproval(null);
      setShowRejectModal(false);
      setRejectNote('');
    },
  });

  const handleApprove = (approval: Approval) => {
    if (window.confirm('Xác nhận duyệt bút toán này?')) {
      approveMutation.mutate(approval.id);
    }
  };

  const handleReject = () => {
    if (selectedApproval) {
      rejectMutation.mutate({ approvalId: selectedApproval.id, note: rejectNote });
    }
  };

  const filteredApprovals = (approvalsList || []).filter((approval: Approval) => {
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        approval.document?.filename?.toLowerCase().includes(q) ||
        approval.document?.vendor_name?.toLowerCase().includes(q) ||
        approval.document?.invoice_no?.toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Duyệt bút toán</h1>
          <p className="text-gray-500 text-sm mt-1">Xem xét và duyệt các đề xuất hạch toán</p>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-2 px-4 py-2 bg-white border rounded-lg hover:bg-gray-50"
        >
          <RefreshCw className="w-4 h-4" />
          Làm mới
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4">
        <div className="flex-1 min-w-[200px]">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Tìm theo tên file, NCC, số HĐ..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
        <div className="flex gap-2">
          {[
            { value: 'pending', label: 'Chờ duyệt', icon: Clock, color: 'yellow' },
            { value: 'approved', label: 'Đã duyệt', icon: CheckCircle, color: 'green' },
            { value: 'rejected', label: 'Từ chối', icon: XCircle, color: 'red' },
            { value: '', label: 'Tất cả', icon: Filter, color: 'gray' },
          ].map(filter => (
            <button
              key={filter.value}
              onClick={() => {
                setStatusFilter(filter.value as typeof statusFilter);
                setPage(1); // Reset page on filter change
              }}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${statusFilter === filter.value
                ? `bg-${filter.color}-100 text-${filter.color}-700 border border-${filter.color}-300`
                : 'bg-white border hover:bg-gray-50'
                }`}
            >
              <filter.icon className="w-4 h-4" />
              {filter.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Approvals List */}
        <div className="lg:col-span-1 bg-white rounded-xl border shadow-sm overflow-hidden flex flex-col h-[700px]">
          <div className="px-4 py-3 border-b bg-gray-50 flex justify-between items-center">
            <h2 className="font-semibold text-gray-900">Danh sách ({totalCount})</h2>
            <div className="text-xs text-gray-500">Trang {page}/{totalPages || 1}</div>
          </div>

          <div className="flex-1 divide-y overflow-auto">
            {isLoading ? (
              <div className="p-8 text-center">
                <RefreshCw className="w-6 h-6 animate-spin mx-auto text-gray-400" />
              </div>
            ) : filteredApprovals.length === 0 ? (
              <div className="p-8 text-center">
                <FileText className="w-10 h-10 mx-auto text-gray-300 mb-3" />
                <p className="text-gray-500">Không có mục nào</p>
              </div>
            ) : (
              filteredApprovals.map((approval: Approval) => (
                <div
                  key={approval.id}
                  onClick={() => setSelectedApproval(approval)}
                  className={`p-4 cursor-pointer hover:bg-gray-50 transition-colors ${selectedApproval?.id === approval.id ? 'bg-blue-50 border-l-4 border-blue-500' : ''
                    }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-gray-900 truncate">
                        {approval.document?.filename || 'Chứng từ'}
                      </p>
                      <p className="text-sm text-gray-500 mt-1">
                        {approval.document?.vendor_name || '-'}
                      </p>
                      {approval.document?.total_amount && (
                        <p className="text-sm font-medium text-gray-900 mt-1">
                          {formatCurrency(approval.document.total_amount)}
                        </p>
                      )}
                    </div>
                    <span className={`inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-medium ${approval.status === 'pending' ? 'bg-yellow-100 text-yellow-700' :
                      approval.status === 'approved' ? 'bg-green-100 text-green-700' :
                        'bg-red-100 text-red-700'
                      }`}>
                      {approval.status === 'pending' ? 'PENDING' :
                        approval.status === 'approved' ? 'APPROVED' : 'REJECTED'}
                    </span>
                  </div>
                  <div className="flex justify-between items-center mt-2">
                    <p className="text-xs text-gray-400">
                      {formatDate(approval.created_at)}
                    </p>
                    {/* Show document ID small for debugging */}
                    {/* <span className="text-[9px] text-gray-300 font-mono">{approval.document_id?.slice(0,8)}</span> */}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Pagination Controls */}
          <div className="p-2 border-t bg-gray-50 flex justify-between items-center">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-2 py-1 text-xs border rounded hover:bg-white disabled:opacity-50"
            >
              Trước
            </button>
            <span className="text-xs text-gray-600">
              {page} / {totalPages || 1}
            </span>
            <button
              onClick={() => setPage(p => Math.min(totalPages || 1, p + 1))}
              disabled={page >= (totalPages || 1)}
              className="px-2 py-1 text-xs border rounded hover:bg-white disabled:opacity-50"
            >
              Sau
            </button>
          </div>
        </div>

        {/* Approval Detail */}
        <div className="lg:col-span-2 bg-white rounded-xl border shadow-sm overflow-hidden h-[700px] flex flex-col">
          {!selectedApproval ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center text-gray-400">
                <Eye className="w-12 h-12 mx-auto mb-4" />
                <p>Chọn một mục để xem chi tiết</p>
              </div>
            </div>
          ) : (
            <>
              <div className="px-4 py-3 border-b bg-gray-50 flex items-center justify-between flex-shrink-0">
                <div>
                  <h2 className="font-semibold text-gray-900">
                    {selectedApproval.document?.filename || 'Chi tiết phê duyệt'}
                  </h2>
                  <p className="text-sm text-gray-500 mt-0.5">
                    {selectedApproval.document?.vendor_name || '-'} • {selectedApproval.document?.invoice_no || '-'}
                  </p>
                </div>
                {selectedApproval.status === 'pending' && (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleApprove(selectedApproval)}
                      disabled={approveMutation.isPending}
                      className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
                    >
                      {approveMutation.isPending ? (
                        <RefreshCw className="w-4 h-4 animate-spin" />
                      ) : (
                        <ThumbsUp className="w-4 h-4" />
                      )}
                      Duyệt
                    </button>
                    <button
                      onClick={() => setShowRejectModal(true)}
                      className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
                    >
                      <ThumbsDown className="w-4 h-4" />
                      Từ chối
                    </button>
                  </div>
                )}
              </div>

              <div className="p-4 overflow-auto flex-1 space-y-6">
                {/* Summary Cards */}
                <div className="grid grid-cols-3 gap-4">
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-xs text-gray-500">Tổng tiền</p>
                    <p className="font-bold text-lg text-gray-900">
                      {formatCurrency(selectedApproval.document?.total_amount)}
                    </p>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-xs text-gray-500">VAT</p>
                    <p className="font-bold text-lg text-gray-900">
                      {formatCurrency(selectedApproval.document?.vat_amount)}
                    </p>
                  </div>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-xs text-gray-500">Ngày HĐ</p>
                    <p className="font-medium text-gray-900">
                      {selectedApproval.document?.invoice_date || '-'}
                    </p>
                  </div>
                </div>

                {/* Journal Entries */}
                {selectedApproval.proposal && (
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="font-semibold text-gray-900">Định khoản đề xuất</h3>
                      {selectedApproval.proposal.is_balanced ? (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-100 text-green-700 rounded text-xs font-medium">
                          <CheckCircle className="w-3.5 h-3.5" />
                          Cân bằng
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-1 bg-red-100 text-red-700 rounded text-xs font-medium">
                          <AlertTriangle className="w-3.5 h-3.5" />
                          Không cân bằng
                        </span>
                      )}
                    </div>
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">TK Nợ</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">TK Có</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500">Số tiền</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Đối tượng</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Diễn giải</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {selectedApproval.proposal.entries?.map((entry: JournalEntryLine, idx: number) => (
                          <tr key={idx}>
                            <td className="px-3 py-2 font-mono">
                              {entry.debit_account || '-'}
                            </td>
                            <td className="px-3 py-2 font-mono">
                              {entry.credit_account || '-'}
                            </td>
                            <td className="px-3 py-2 text-right font-medium">
                              {formatCurrency(entry.amount)}
                            </td>
                            <td className="px-3 py-2 text-gray-600">
                              {entry.object_code || '-'}
                            </td>
                            <td className="px-3 py-2 text-gray-600 max-w-[150px] truncate">
                              {entry.description || '-'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot className="bg-gray-50 font-medium">
                        <tr>
                          <td colSpan={2} className="px-3 py-2 text-right text-gray-700">Tổng:</td>
                          <td className="px-3 py-2 text-right">
                            {formatCurrency(selectedApproval.proposal.total_debit)}
                          </td>
                          <td colSpan={2}></td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                )}

                {/* Reviewer Note */}
                {selectedApproval.reviewer_note && (
                  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                    <p className="text-sm font-medium text-yellow-800">Ghi chú từ người duyệt</p>
                    <p className="mt-1 text-sm text-yellow-700">{selectedApproval.reviewer_note}</p>
                    {selectedApproval.reviewer && (
                      <p className="mt-2 text-xs text-yellow-600">
                        Bởi: {selectedApproval.reviewer} • {formatDate(selectedApproval.resolved_at || '')}
                      </p>
                    )}
                  </div>
                )}

                {/* View Document Link */}
                <button
                  onClick={() => {
                    // Prefer the top-level document_id from the approval item
                    const docId = selectedApproval.document_id || selectedApproval.proposal?.document_id || selectedApproval.document?.id;
                    if (docId) {
                      navigate(`/documents/${docId}`);
                    } else {
                      alert("Không tìm thấy ID chứng từ");
                    }
                  }}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 border rounded-lg hover:bg-gray-50 border-blue-200 text-blue-700 bg-blue-50/50"
                >
                  <Eye className="w-4 h-4" />
                  Xem chứng từ gốc & Lịch sử
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Reject Modal */}
      {showRejectModal && selectedApproval && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
            <h3 className="text-lg font-semibold text-gray-900">Từ chối phê duyệt</h3>
            <p className="text-sm text-gray-500 mt-1">
              Vui lòng nhập lý do từ chối
            </p>
            <textarea
              value={rejectNote}
              onChange={e => setRejectNote(e.target.value)}
              placeholder="Lý do từ chối..."
              className="w-full mt-4 p-3 border rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500"
              rows={4}
            />
            <div className="flex justify-end gap-3 mt-4">
              <button
                onClick={() => {
                  setShowRejectModal(false);
                  setRejectNote('');
                }}
                className="px-4 py-2 border rounded-lg hover:bg-gray-50"
              >
                Hủy
              </button>
              <button
                onClick={handleReject}
                disabled={rejectMutation.isPending || !rejectNote.trim()}
                className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
              >
                {rejectMutation.isPending ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <XCircle className="w-4 h-4" />
                )}
                Từ chối
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
