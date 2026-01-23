import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Send,
  RefreshCw,
  Lightbulb,
  Calculator,
} from 'lucide-react';
import api from '../lib/api';
import type {  JournalEntryLine } from '../types';

function formatCurrency(amount: number | undefined): string {
  if (amount === undefined || amount === null) return '-';
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount);
}

export default function JournalProposalPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showReasoning, setShowReasoning] = useState<string | null>(null);

  // Fetch document and proposal
  const { data: doc, isLoading: docLoading } = useQuery({
    queryKey: ['document', id],
    queryFn: () => api.getDocument(id!),
    enabled: !!id,
  });

  const { data: proposal, isLoading: proposalLoading } = useQuery({
    queryKey: ['document-proposal', id],
    queryFn: () => api.getDocumentProposal(id!),
    enabled: !!id,
  });

  // Submit for approval
  const submitMutation = useMutation({
    mutationFn: () => api.submitApproval(id!, proposal?.id || ""),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['document', id] });
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      navigate('/approvals');
    },
  });

  const isLoading = docLoading || proposalLoading;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    );
  }

  if (!doc || !proposal) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Không tìm thấy đề xuất hạch toán</p>
        <button
          onClick={() => navigate(`/documents/${id}`)}
          className="mt-4 text-blue-600 hover:underline"
        >
          Quay lại chứng từ
        </button>
      </div>
    );
  }

  const isBalanced = Math.abs(proposal.total_debit - proposal.total_credit) < 0.01;
  const canSubmit = isBalanced && proposal.entries.length > 0 && 
    !['pending_approval', 'approved', 'posted'].includes(doc.status);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate(`/documents/${id}`)}
            className="p-2 hover:bg-gray-100 rounded-lg"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-xl font-bold text-gray-900">Đề xuất hạch toán</h1>
            <p className="text-sm text-gray-500 mt-1">
              Chứng từ: {doc.filename}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {canSubmit && (
            <button
              onClick={() => submitMutation.mutate()}
              disabled={submitMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              {submitMutation.isPending ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
              Gửi duyệt
            </button>
          )}
        </div>
      </div>

      {/* Balance Status */}
      <div className={`rounded-xl p-4 flex items-center justify-between ${
        isBalanced ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'
      }`}>
        <div className="flex items-center gap-3">
          {isBalanced ? (
            <CheckCircle className="w-6 h-6 text-green-600" />
          ) : (
            <XCircle className="w-6 h-6 text-red-600" />
          )}
          <div>
            <p className={`font-medium ${isBalanced ? 'text-green-700' : 'text-red-700'}`}>
              {isBalanced ? 'Bút toán cân bằng' : 'Bút toán chưa cân bằng'}
            </p>
            <p className={`text-sm ${isBalanced ? 'text-green-600' : 'text-red-600'}`}>
              Tổng Nợ: {formatCurrency(proposal.total_debit)} | Tổng Có: {formatCurrency(proposal.total_credit)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Calculator className="w-5 h-5 text-gray-400" />
          <span className="text-sm text-gray-600">
            Chênh lệch: {formatCurrency(Math.abs(proposal.total_debit - proposal.total_credit))}
          </span>
        </div>
      </div>

      {/* Proposal Info */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border p-4">
          <p className="text-sm text-gray-500">Ngày hạch toán</p>
          <p className="font-medium text-gray-900 mt-1">
            {proposal.posting_date ? new Date(proposal.posting_date).toLocaleDateString('vi-VN') : 'Chưa xác định'}
          </p>
        </div>
        <div className="bg-white rounded-xl border p-4">
          <p className="text-sm text-gray-500">Diễn giải</p>
          <p className="font-medium text-gray-900 mt-1">
            {proposal.description || `Hạch toán ${doc.filename}`}
          </p>
        </div>
        <div className="bg-white rounded-xl border p-4">
          <p className="text-sm text-gray-500">Trạng thái</p>
          <p className={`font-medium mt-1 ${
            proposal.status === 'approved' ? 'text-green-600' :
            proposal.status === 'rejected' ? 'text-red-600' :
            proposal.status === 'pending' ? 'text-yellow-600' :
            'text-gray-600'
          }`}>
            {proposal.status === 'approved' ? 'Đã duyệt' :
             proposal.status === 'rejected' ? 'Từ chối' :
             proposal.status === 'pending' ? 'Chờ duyệt' :
             'Bản nháp'}
          </p>
        </div>
      </div>

      {/* Journal Entries Table */}
      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        <div className="px-4 py-3 border-b bg-gray-50 flex items-center justify-between">
          <h2 className="font-semibold text-gray-900">Định khoản</h2>
          <span className="text-sm text-gray-500">{proposal.entries.length} dòng</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">STT</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">TK Nợ</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">TK Có</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Số tiền</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Diễn giải</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Đối tượng</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Độ tin cậy</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Giải thích</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {proposal.entries.map((entry: JournalEntryLine, idx: number) => (
                <tr key={entry.id || idx} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm text-gray-500">{idx + 1}</td>
                  <td className="px-4 py-3">
                    {entry.debit_account && (
                      <div>
                        <span className="font-mono text-sm font-medium text-gray-900">
                          {entry.debit_account}
                        </span>
                        {entry.debit_account_name && (
                          <p className="text-xs text-gray-500">{entry.debit_account_name}</p>
                        )}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {entry.credit_account && (
                      <div>
                        <span className="font-mono text-sm font-medium text-gray-900">
                          {entry.credit_account}
                        </span>
                        {entry.credit_account_name && (
                          <p className="text-xs text-gray-500">{entry.credit_account_name}</p>
                        )}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-medium text-gray-900">
                    {formatCurrency(entry.amount)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 max-w-[200px] truncate">
                    {entry.description || '-'}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {entry.object_code && (
                      <div>
                        <span className="font-mono">{entry.object_code}</span>
                        {entry.object_name && (
                          <p className="text-xs text-gray-500">{entry.object_name}</p>
                        )}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {entry.confidence !== undefined && (
                      <span className={`inline-flex px-2 py-1 rounded text-xs font-medium ${
                        entry.confidence >= 0.8 ? 'bg-green-100 text-green-700' :
                        entry.confidence >= 0.5 ? 'bg-yellow-100 text-yellow-700' :
                        'bg-red-100 text-red-700'
                      }`}>
                        {Math.round(entry.confidence * 100)}%
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {entry.reasoning && (
                      <button
                        onClick={() => setShowReasoning(showReasoning === entry.id ? null : entry.id || `${idx}`)}
                        className="p-1.5 hover:bg-gray-100 rounded"
                        title="Xem giải thích"
                      >
                        <Lightbulb className={`w-4 h-4 ${
                          showReasoning === (entry.id || `${idx}`) ? 'text-yellow-500' : 'text-gray-400'
                        }`} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot className="bg-gray-50 border-t font-medium">
              <tr>
                <td colSpan={3} className="px-4 py-3 text-right text-sm text-gray-700">Tổng cộng:</td>
                <td className="px-4 py-3 text-right text-gray-900">
                  {formatCurrency(proposal.total_debit)}
                </td>
                <td colSpan={4}></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      {/* Reasoning Panel */}
      {showReasoning && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4">
          <div className="flex items-start gap-3">
            <Lightbulb className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-yellow-800">Giải thích định khoản</p>
              <p className="mt-1 text-sm text-yellow-700">
                {proposal.entries.find((e: JournalEntryLine) => (e.id || '') === showReasoning)?.reasoning ||
                 proposal.entries[parseInt(showReasoning)]?.reasoning ||
                 'Không có giải thích'}
              </p>
              <p className="mt-2 text-xs text-yellow-600">
                Nguồn: Rule-based / Knowledge Base / LLM inference
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Submission Note */}
      {canSubmit && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-blue-800">Lưu ý trước khi gửi duyệt</p>
              <ul className="mt-2 text-sm text-blue-700 list-disc list-inside space-y-1">
                <li>Kiểm tra lại các tài khoản Nợ/Có</li>
                <li>Đảm bảo bút toán cân bằng (Tổng Nợ = Tổng Có)</li>
                <li>Xác nhận mã đối tượng (khách hàng/NCC) chính xác</li>
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
