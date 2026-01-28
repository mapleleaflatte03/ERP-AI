import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  FileText,
  RefreshCw,
  Zap,
  FileCheck,
  Info,
  BookOpen,
  Send,
  ThumbsUp,
} from 'lucide-react';
import api from '../lib/api';

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  new: { label: 'Mới', color: 'bg-gray-100 text-gray-700' },
  extracting: { label: 'Đang trích xuất', color: 'bg-blue-100 text-blue-700' },
  extracted: { label: 'Đã trích xuất', color: 'bg-cyan-100 text-cyan-700' },
  proposing: { label: 'Đang đề xuất', color: 'bg-purple-100 text-purple-700' },
  proposed: { label: 'Có đề xuất', color: 'bg-indigo-100 text-indigo-700' },
  pending_approval: { label: 'Chờ duyệt', color: 'bg-yellow-100 text-yellow-700' },
  approved: { label: 'Đã duyệt', color: 'bg-green-100 text-green-700' },
  rejected: { label: 'Từ chối', color: 'bg-red-100 text-red-700' },
  posted: { label: 'Đã ghi sổ', color: 'bg-emerald-100 text-emerald-700' },
};

function formatCurrency(amount: number | undefined): string {
  if (amount === undefined || amount === null) return '-';
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount);
}

function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '-';
  try {
    return new Date(dateStr).toLocaleDateString('vi-VN', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

function formatDateTime(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleString('vi-VN');
  } catch {
    return dateStr;
  }
}

export default function DocumentDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'extracted' | 'proposal' | 'ledger' | 'evidence'>('extracted');

  // Fetch document
  const { data: doc, isLoading } = useQuery({
    queryKey: ['document', id],
    queryFn: () => api.getDocument(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return ['extracting', 'proposing'].includes(status) ? 1000 : false;
    }
  });

  // Fetch proposal (if exists)
  const { data: proposal } = useQuery({
    queryKey: ['document-proposal', id],
    queryFn: () => api.getDocumentProposal(id!),
    enabled: !!id && ['proposed', 'pending_approval', 'approved', 'rejected', 'posted'].includes(doc?.status),
    retry: false
  });

  // Fetch ledger (if posted)
  const { data: ledger } = useQuery({
    queryKey: ['document-ledger', id],
    queryFn: () => api.getDocumentLedger(id!),
    enabled: !!id && ['posted'].includes(doc?.status),
    retry: false
  });

  // Fetch evidence timeline
  const { data: evidence = [] } = useQuery({
    queryKey: ['document-evidence', id],
    queryFn: () => api.getDocumentEvidence(id!),
    enabled: !!id,
  });

  // Actions
  const extractMutation = useMutation({
    mutationFn: () => api.runExtraction(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['document', id] });
      queryClient.invalidateQueries({ queryKey: ['documents'] }); // Invalidate global list
      queryClient.invalidateQueries({ queryKey: ['document-evidence', id] });
    },
  });

  const proposeMutation = useMutation({
    mutationFn: () => api.runProposal(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['document', id] });
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      queryClient.invalidateQueries({ queryKey: ['document-evidence', id] });
      setActiveTab('proposal');
    },
  });

  const submitMutation = useMutation({
    mutationFn: (proposalId: string) => api.submitApproval(id!, proposalId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['document', id] });
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      queryClient.invalidateQueries({ queryKey: ['document-proposal', id] });
      // Store approval ID if needed, or just rely on status update
    },
  });

  const approveMutation = useMutation({
    mutationFn: (approvalId: string) => api.approveDocument(approvalId, 'Approved via UI'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['document', id] });
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      queryClient.invalidateQueries({ queryKey: ['document-ledger', id] });
      setActiveTab('ledger');
    }
  });


  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Không tìm thấy chứng từ</p>
      </div>
    );
  }

  const statusCfg = STATUS_CONFIG[doc.status] || STATUS_CONFIG.new;
  const canExtract = ['new', 'extracting'].includes(doc.status); // Allow retry if stuck?
  const canPropose = ['extracted'].includes(doc.status);
  const canSubmit = ['proposed'].includes(doc.status) && proposal?.id;
  const canApprove = ['pending_approval'].includes(doc.status) && proposal?.approval_id;

  // Extracted fields
  const extractedFields = doc.extracted_data || doc.extracted_fields || {};
  // Handle case where fields are directly on doc
  const displayFields = [
    { key: 'invoice_no', label: 'Số hóa đơn', value: doc.invoice_no || extractedFields.invoice_no || extractedFields.invoice_number },
    { key: 'invoice_date', label: 'Ngày hóa đơn', value: formatDate(doc.invoice_date || extractedFields.invoice_date) },
    { key: 'vendor_name', label: 'Nhà cung cấp', value: doc.vendor_name || extractedFields.vendor_name || extractedFields.supplier_name },
    { key: 'vendor_tax_id', label: 'MST', value: doc.vendor_tax_id || extractedFields.vendor_tax_id || extractedFields.tax_id },
    { key: 'total_amount', label: 'Tổng tiền', value: formatCurrency(doc.total_amount || extractedFields.total_amount) },
    { key: 'vat_amount', label: 'Thuế VAT', value: formatCurrency(doc.vat_amount || extractedFields.tax_amount || extractedFields.vat_amount) },
    { key: 'currency', label: 'Loại tiền', value: doc.currency || extractedFields.currency || 'VND' },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/documents')}
            className="p-2 hover:bg-gray-100 rounded-lg"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-xl font-bold text-gray-900 flex items-center gap-3">
              <FileText className="w-6 h-6 text-gray-400" />
              {doc.filename}
            </h1>
            <div className="flex items-center gap-3 mt-1">
              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusCfg.color}`}>
                {statusCfg.label}
              </span>
              <span className="text-sm text-gray-500">
                Tạo lúc: {formatDateTime(doc.created_at)}
              </span>
            </div>
          </div>
        </div>

        {/* Actions Toolbar */}
        <div className="flex items-center gap-3">
          {/* Re-run operations */}
          {!['new', 'extracting'].includes(doc.status) && (
            <button onClick={() => extractMutation.mutate()} className="p-2 text-gray-400 hover:text-blue-600" title="Re-run Extraction">
              <RefreshCw className={`w-4 h-4 ${extractMutation.isPending ? 'animate-spin' : ''}`} />
            </button>
          )}

          {canExtract && (
            <button
              onClick={() => extractMutation.mutate()}
              disabled={extractMutation.isPending || doc.status === 'extracting'}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {extractMutation.isPending || doc.status === 'extracting' ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Zap className="w-4 h-4" />
              )}
              {doc.status === 'extracting' ? 'Đang trích xuất...' : 'Trích xuất'}
            </button>
          )}

          {canPropose && (
            <button
              onClick={() => proposeMutation.mutate()}
              disabled={proposeMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
            >
              {proposeMutation.isPending ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <FileCheck className="w-4 h-4" />
              )}
              Đề xuất
            </button>
          )}

          {canSubmit && (
            <button
              onClick={() => submitMutation.mutate(proposal.id)}
              disabled={submitMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
            >
              {submitMutation.isPending ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              Gửi duyệt
            </button>
          )}

          {canApprove && (
            <button
              onClick={() => approveMutation.mutate(proposal.approval_id)}
              disabled={approveMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              {approveMutation.isPending ? <RefreshCw className="w-4 h-4 animate-spin" /> : <ThumbsUp className="w-4 h-4" />}
              Duyệt ngay
            </button>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Panel: Preview */}
        <div className="bg-white rounded-xl border shadow-sm overflow-hidden flex flex-col h-[600px]">
          <div className="px-4 py-3 border-b bg-gray-50">
            <h2 className="font-semibold text-gray-900">Xem trước file</h2>
          </div>
          <div className="flex-1 bg-gray-100 flex items-center justify-center p-4 overflow-hidden relative">
            {doc.file_path || doc.minio_key ? (
              // Use proper URL based on environment/proxy setup for accessing minio content if needed
              // For now, assume API might proxy it or we have a link.
              // Since real backend uses minio, we might not have a public URL unless signed.
              // UI fallback:
              <div className="text-center text-gray-500">
                <p className="mb-2">Preview (PDF/Image)</p>
                <p className="text-xs">File: {doc.filename}</p>
                {/* Emulate iframe if supported, else placehoder */}
              </div>
            ) : (
              <div className="text-center text-gray-400">
                <FileText className="w-16 h-16 mx-auto mb-4" />
                <p>Không có bản xem trước</p>
              </div>
            )}
          </div>
        </div>

        {/* Right Panel: Tabs */}
        <div className="bg-white rounded-xl border shadow-sm overflow-hidden flex flex-col h-[600px]">
          <div className="border-b">
            <nav className="flex overflow-x-auto">
              <button onClick={() => setActiveTab('extracted')} className={`px-4 py-3 text-sm font-medium border-b-2 whitespace-nowrap ${activeTab === 'extracted' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
                Trích xuất
              </button>
              <button onClick={() => setActiveTab('proposal')} className={`px-4 py-3 text-sm font-medium border-b-2 whitespace-nowrap ${activeTab === 'proposal' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
                Đề xuất
              </button>
              <button onClick={() => setActiveTab('ledger')} className={`px-4 py-3 text-sm font-medium border-b-2 whitespace-nowrap ${activeTab === 'ledger' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
                Sổ cái
              </button>
              <button onClick={() => setActiveTab('evidence')} className={`px-4 py-3 text-sm font-medium border-b-2 whitespace-nowrap ${activeTab === 'evidence' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
                Lịch sử
              </button>
            </nav>
          </div>

          <div className="flex-1 overflow-auto p-4">
            {activeTab === 'extracted' && (
              <div className="space-y-6">
                <section>
                  <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-3">Thông tin chung</h3>
                  <dl className="grid grid-cols-2 gap-4">
                    {displayFields.map(field => (
                      <div key={field.key} className="bg-gray-50 rounded-lg p-3">
                        <dt className="text-xs text-gray-500 uppercase">{field.label}</dt>
                        <dd className="mt-1 text-sm font-medium text-gray-900">{field.value || '-'}</dd>
                      </div>
                    ))}
                  </dl>
                </section>
                {doc.raw_text && (
                  <section>
                    <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Raw Text (OCR)</h3>
                    <pre className="text-xs bg-gray-50 p-2 rounded border max-h-40 overflow-auto whitespace-pre-wrap">{doc.raw_text}</pre>
                  </section>
                )}
              </div>
            )}

            {activeTab === 'proposal' && (
              <div className="space-y-4">
                {proposal ? (
                  <>
                    <div className="bg-indigo-50 p-4 rounded-lg mb-4">
                      <h3 className="font-semibold text-indigo-900 mb-2">AI Reasoning</h3>
                      <p className="text-sm text-indigo-800">{proposal.ai_reasoning || proposal.explanation || 'No reasoning provided.'}</p>
                      <div className="mt-2 text-xs text-indigo-600 font-medium">Confidence: {(proposal.ai_confidence * 100).toFixed(1)}%</div>
                    </div>

                    <h3 className="font-medium text-gray-900">Bút toán đề xuất</h3>
                    <div className="border rounded-lg overflow-hidden">
                      <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Account</th>
                            <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Debit</th>
                            <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Credit</th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                          {proposal.entries?.map((entry: any, idx: number) => (
                            <tr key={idx}>
                              <td className="px-3 py-2 text-sm text-gray-900">
                                <div className="font-medium">{entry.account_code}</div>
                                <div className="text-xs text-gray-500">{entry.account_name}</div>
                              </td>
                              <td className="px-3 py-2 text-sm text-gray-900 text-right">{entry.debit_amount || entry.debit ? formatCurrency(entry.debit_amount || entry.debit) : '-'}</td>
                              <td className="px-3 py-2 text-sm text-gray-900 text-right">{entry.credit_amount || entry.credit ? formatCurrency(entry.credit_amount || entry.credit) : '-'}</td>
                            </tr>
                          ))}
                        </tbody>
                        <tfoot className="bg-gray-50">
                          <tr>
                            <td className="px-3 py-2 text-sm font-medium text-gray-900">Total</td>
                            <td className="px-3 py-2 text-sm font-medium text-gray-900 text-right">{formatCurrency(proposal.total_debit)}</td>
                            <td className="px-3 py-2 text-sm font-medium text-gray-900 text-right">{formatCurrency(proposal.total_credit)}</td>
                          </tr>
                        </tfoot>
                      </table>
                    </div>
                  </>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <Info className="w-12 h-12 mx-auto mb-2 text-gray-300" />
                    <p>Chưa có đề xuất hạch toán.</p>
                    {canPropose && <p className="text-xs mt-2">Nhấn "Đề xuất" đề AI phân tích.</p>}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'ledger' && (
              <div className="space-y-4">
                {ledger ? (
                  <>
                    <div className="flex items-center gap-2 mb-4">
                      <div className="p-2 bg-green-100 rounded-full"><BookOpen className="w-5 h-5 text-green-600" /></div>
                      <div>
                        <div className="font-semibold text-gray-900">{ledger.entry_number}</div>
                        <div className="text-xs text-gray-500">Posted by {ledger.posted_by_name} on {formatDate(ledger.entry_date)}</div>
                      </div>
                    </div>
                    {/* Re-use table or component for lines */}
                    <div className="border rounded-lg overflow-hidden">
                      {/* Similar table structure to proposal but using ledger lines */}
                      {/* Omitting for brevity, reusing simplistic view */}
                      <pre className="text-xs p-2 bg-gray-50">{JSON.stringify(ledger.lines || ledger, null, 2)}</pre>
                    </div>
                  </>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <p>Chứng từ chưa được ghi sổ cái.</p>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'evidence' && (
              <div className="space-y-4">
                {evidence.length === 0 ? <p className="text-gray-500">Chưa có dữ liệu.</p> : (
                  <div className="relative">
                    <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-200"></div>
                    <div className="space-y-6">
                      {evidence.map((ev: any, i: number) => (
                        <div key={i} className="relative pl-10">
                          <div className={`absolute left-2.5 w-3 h-3 rounded-full border-2 bg-white -ml-px ${ev.severity === 'error' ? 'border-red-500' : 'border-blue-500'}`}></div>
                          <div>
                            <div className="text-sm font-medium text-gray-900">{ev.step} - {ev.action}</div>
                            <div className="text-xs text-gray-500">{formatDateTime(ev.timestamp)}</div>
                            {ev.output_summary && <div className="mt-1 text-sm text-gray-600 bg-gray-50 p-2 rounded">{ev.output_summary}</div>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
