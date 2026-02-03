import { useState, lazy, Suspense } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  CheckCircle2,
  XCircle,
  ChevronLeft,
  ChevronRight,
  Filter,
  FileText,
  Clock,
  AlertCircle,
  Eye,
  Loader2,
  MessageSquare,
} from 'lucide-react';
import api from '../lib/api';
import type { Approval } from '../types';

import { Link } from 'react-router-dom';

// Lazy load chat component
const ModuleChatDock = lazy(() => import('../components/moduleChat/ModuleChatDock'));

function RiskBadge({ level }: { level?: string }) {
  if (!level) return null;
  const colors: Record<string, string> = {
    low: 'bg-green-100 text-green-700',
    medium: 'bg-yellow-100 text-yellow-700',
    high: 'bg-red-100 text-red-700',
  };
  return (
    <span className={`px-2 py-0.5 text-xs rounded ${colors[level] || colors.medium}`}>
      {level === 'low' ? 'Thấp' : level === 'medium' ? 'Trung bình' : 'Cao'}
    </span>
  );
}

export default function ApprovalsInbox() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>('pending');
  const [page, setPage] = useState(1);
  const [showChat, setShowChat] = useState(false);
  const limit = 10;

  // Fetch approvals
  const { data: response, isLoading, refetch } = useQuery({
    queryKey: ['approvals', statusFilter, page, limit],
    queryFn: () => api.getApprovals(statusFilter || undefined, limit, (page - 1) * limit),
  });

  // Handle potential object response { approvals: [], count: ... } or array []
  // Also handle wrapped response { success: true, data: { approvals: [...] } }
  const unwrappedResponse = (response && typeof response === 'object' && 'data' in response)
    ? response.data
    : response;

  const approvalsList = Array.isArray(response)
    ? response
    : (unwrappedResponse && typeof unwrappedResponse === 'object' && 'approvals' in unwrappedResponse)
      ? (unwrappedResponse.approvals || [])
      : [];

  const totalCount = (unwrappedResponse && !Array.isArray(unwrappedResponse) && ('count' in unwrappedResponse || 'total' in unwrappedResponse || 'pending_count' in unwrappedResponse))
    ? (unwrappedResponse.count || unwrappedResponse.total || unwrappedResponse.pending_count || approvalsList.length)
    : approvalsList.length;

  const totalPages = Math.max(1, Math.ceil(totalCount / limit));

  // Approve mutation
  const approveMutation = useMutation({
    mutationFn: (approvalId: string) => api.approveDocument(approvalId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      alert('Đã duyệt thành công');
    },
    onError: () => {
      alert('Lỗi khi duyệt');
    },
  });

  // Reject mutation
  const rejectMutation = useMutation({
    mutationFn: ({ approvalId, reason }: { approvalId: string; reason: string }) =>
      api.rejectDocument(approvalId, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      alert('Đã từ chối');
    },
    onError: () => {
      alert('Lỗi khi từ chối');
    },
  });

  const handleApprove = (approvalId: string) => {
    if (confirm('Xác nhận duyệt bút toán này?')) {
      approveMutation.mutate(approvalId);
    }
  };

  const handleReject = (approvalId: string) => {
    const reason = prompt('Nhập lý do từ chối:');
    if (reason) {
      rejectMutation.mutate({ approvalId, reason });
    }
  };

  const filteredApprovals = (approvalsList || []).filter((approval: Approval) => {
    if (statusFilter && statusFilter !== 'all') {
      return approval.status === statusFilter;
    }
    return true;
  });

  const statusOptions = [
    { value: 'pending', label: 'Chờ duyệt', icon: Clock },
    { value: 'approved', label: 'Đã duyệt', icon: CheckCircle2 },
    { value: 'rejected', label: 'Đã từ chối', icon: XCircle },
    { value: '', label: 'Tất cả', icon: Filter },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Duyệt bút toán</h1>
          <p className="text-gray-500 text-sm mt-1">
            Danh sách ({totalCount})
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          Làm mới
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        {statusOptions.map((option) => {
          const Icon = option.icon;
          return (
            <button
              key={option.value}
              onClick={() => {
                setStatusFilter(option.value);
                setPage(1);
              }}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition ${
                statusFilter === option.value
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              <Icon className="w-4 h-4" />
              {option.label}
            </button>
          );
        })}
      </div>

      {/* List */}
      <div className="bg-white rounded-xl border overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center">
            <Loader2 className="w-8 h-8 mx-auto text-blue-600 animate-spin" />
            <p className="text-gray-500 mt-2">Đang tải...</p>
          </div>
        ) : filteredApprovals.length === 0 ? (
          <div className="p-12 text-center">
            <AlertCircle className="w-12 h-12 mx-auto text-gray-300 mb-4" />
            <p className="text-gray-500">Không có mục nào</p>
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Chứng từ
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Nhà cung cấp
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Số tiền
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Độ tin cậy AI
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Rủi ro
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Trạng thái
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  Thao tác
                </th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {filteredApprovals.map((approval: Approval) => (
                <tr key={approval.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <FileText className="w-5 h-5 text-gray-400" />
                      <div>
                        <p className="font-medium text-gray-900">
                          {approval.invoice_number || approval.filename || 'N/A'}
                        </p>
                        <p className="text-xs text-gray-500">
                          {approval.invoice_date || '-'}
                        </p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700">
                    {approval.vendor_name || '-'}
                  </td>
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">
                    {approval.total_amount
                      ? new Intl.NumberFormat('vi-VN', { style: 'currency', currency: approval.currency || 'VND' }).format(approval.total_amount)
                      : '-'}
                  </td>
                  <td className="px-4 py-3">
                    {approval.ai_confidence !== null && approval.ai_confidence !== undefined ? (
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              approval.ai_confidence >= 0.8
                                ? 'bg-green-500'
                                : approval.ai_confidence >= 0.6
                                ? 'bg-yellow-500'
                                : 'bg-red-500'
                            }`}
                            style={{ width: `${approval.ai_confidence * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-gray-500">
                          {(approval.ai_confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    ) : (
                      <span className="text-gray-400">-</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <RiskBadge level={approval.risk_level} />
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-1 text-xs rounded-full ${
                        approval.status === 'approved'
                          ? 'bg-green-100 text-green-700'
                          : approval.status === 'rejected'
                          ? 'bg-red-100 text-red-700'
                          : 'bg-yellow-100 text-yellow-700'
                      }`}
                    >
                      {approval.status === 'approved'
                        ? 'Đã duyệt'
                        : approval.status === 'rejected'
                        ? 'Từ chối'
                        : 'Chờ duyệt'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      {approval.job_id && (
                        <Link
                          to={`/documents/${approval.job_id}`}
                          className="p-2 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg"
                          title="Xem chi tiết"
                        >
                          <Eye className="w-4 h-4" />
                        </Link>
                      )}
                      {approval.status === 'pending' && (
                        <>
                          <button
                            onClick={() => handleApprove(approval.id)}
                            className="p-2 text-green-600 hover:bg-green-50 rounded-lg"
                            title="Duyệt"
                            disabled={approveMutation.isPending}
                          >
                            <CheckCircle2 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleReject(approval.id)}
                            className="p-2 text-red-600 hover:bg-red-50 rounded-lg"
                            title="Từ chối"
                            disabled={rejectMutation.isPending}
                          >
                            <XCircle className="w-4 h-4" />
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500">
            Trang {page} / {totalPages}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="p-2 rounded-lg bg-gray-100 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="p-2 rounded-lg bg-gray-100 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}

      {/* Module Chat Dock */}
      {showChat && (
        <Suspense fallback={null}>
          <ModuleChatDock 
            module="approvals" 
            onClose={() => setShowChat(false)} 
          />
        </Suspense>
      )}
      
      {/* Chat Toggle Button */}
      {!showChat && (
        <button
          onClick={() => setShowChat(true)}
          className="fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-3 bg-green-600 text-white rounded-full shadow-lg hover:bg-green-700 transition-all hover:scale-105"
          title="Mở AI Chat cho Duyệt chứng từ"
        >
          <span>✅</span>
          <MessageSquare className="w-5 h-5" />
        </button>
      )}
    </div>
  );
}
