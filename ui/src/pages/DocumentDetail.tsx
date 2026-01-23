import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  FileText,
  CheckCircle,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Zap,
  FileCheck,
  Eye,
  Info,
  ChevronRight,
} from 'lucide-react';
import api from '../lib/api';
import type {  EvidenceEvent } from '../types';

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
  return new Date(dateStr).toLocaleDateString('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

function formatDateTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString('vi-VN');
}

export default function DocumentDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'extracted' | 'validation' | 'evidence'>('extracted');

  // Fetch document
  const { data: doc, isLoading } = useQuery({
    queryKey: ['document', id],
    queryFn: () => api.getDocument(id!),
    enabled: !!id,
  });

  // Fetch evidence timeline
  const { data: evidence = [] } = useQuery({
    queryKey: ['document-evidence', id],
    queryFn: () => api.getDocumentEvidence(id!),
    enabled: !!id,
  });

  // Run extraction mutation
  const extractMutation = useMutation({
    mutationFn: () => api.runExtraction(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['document', id] });
      queryClient.invalidateQueries({ queryKey: ['document-evidence', id] });
    },
  });

  // Run proposal mutation  
  const proposeMutation = useMutation({
    mutationFn: () => api.runProposal(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['document', id] });
      navigate(`/documents/${id}/proposal`);
    },
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
  const canExtract = ['new'].includes(doc.status);
  const canPropose = ['extracted'].includes(doc.status);
  const hasProposal = ['proposed', 'pending_approval', 'approved', 'rejected', 'posted'].includes(doc.status);

  // Extracted fields to display
  const extractedFields = doc.extracted_fields || {};
  const fieldsList = [
    { key: 'invoice_no', label: 'Số hóa đơn', value: doc.invoice_no || extractedFields.invoice_no },
    { key: 'invoice_date', label: 'Ngày hóa đơn', value: formatDate(doc.invoice_date || extractedFields.invoice_date) },
    { key: 'vendor_name', label: 'Nhà cung cấp', value: doc.vendor_name || extractedFields.vendor_name },
    { key: 'vendor_tax_id', label: 'MST', value: doc.vendor_tax_id || extractedFields.vendor_tax_id },
    { key: 'total_amount', label: 'Tổng tiền', value: formatCurrency(doc.total_amount || extractedFields.total_amount) },
    { key: 'vat_amount', label: 'Thuế VAT', value: formatCurrency(doc.vat_amount || extractedFields.vat_amount) },
    { key: 'currency', label: 'Loại tiền', value: doc.currency || extractedFields.currency || 'VND' },
  ];

  // Validation warnings (mock for now)
  const validationWarnings = [
    ...(doc.vendor_tax_id ? [] : [{ severity: 'warning', message: 'Chưa có MST nhà cung cấp' }]),
    ...(doc.total_amount ? [] : [{ severity: 'error', message: 'Chưa trích xuất được tổng tiền' }]),
    ...(doc.invoice_no ? [] : [{ severity: 'warning', message: 'Chưa có số hóa đơn' }]),
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
        <div className="flex items-center gap-3">
          {canExtract && (
            <button
              onClick={() => extractMutation.mutate()}
              disabled={extractMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {extractMutation.isPending ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Zap className="w-4 h-4" />
              )}
              Trích xuất
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
              Đề xuất hạch toán
            </button>
          )}
          {hasProposal && (
            <button
              onClick={() => navigate(`/documents/${id}/proposal`)}
              className="flex items-center gap-2 px-4 py-2 bg-white border rounded-lg hover:bg-gray-50"
            >
              <Eye className="w-4 h-4" />
              Xem đề xuất
              <ChevronRight className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Main Content - 4 Panel Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Panel A: File Preview */}
        <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b bg-gray-50">
            <h2 className="font-semibold text-gray-900">Xem trước file</h2>
          </div>
          <div className="p-4 h-[500px] flex items-center justify-center bg-gray-100">
            {doc.file_url ? (
              doc.filename.toLowerCase().endsWith('.pdf') ? (
                <iframe
                  src={doc.file_url}
                  className="w-full h-full border-0"
                  title="PDF Preview"
                />
              ) : (
                <img
                  src={doc.file_url}
                  alt={doc.filename}
                  className="max-w-full max-h-full object-contain"
                />
              )
            ) : (
              <div className="text-center text-gray-400">
                <FileText className="w-16 h-16 mx-auto mb-4" />
                <p>Không có bản xem trước</p>
              </div>
            )}
          </div>
        </div>

        {/* Panel B, C, D: Tabs */}
        <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
          <div className="border-b">
            <nav className="flex">
              <button
                onClick={() => setActiveTab('extracted')}
                className={`flex-1 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'extracted'
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                Dữ liệu trích xuất
              </button>
              <button
                onClick={() => setActiveTab('validation')}
                className={`flex-1 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'validation'
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                Kiểm tra
                {validationWarnings.length > 0 && (
                  <span className="ml-2 px-1.5 py-0.5 text-xs bg-yellow-100 text-yellow-700 rounded">
                    {validationWarnings.length}
                  </span>
                )}
              </button>
              <button
                onClick={() => setActiveTab('evidence')}
                className={`flex-1 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'evidence'
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                Lịch sử xử lý
              </button>
            </nav>
          </div>

          <div className="p-4 h-[456px] overflow-auto">
            {/* Panel B: Extracted Fields */}
            {activeTab === 'extracted' && (
              <div className="space-y-4">
                <h3 className="font-medium text-gray-900">Thông tin trích xuất từ OCR</h3>
                <dl className="grid grid-cols-2 gap-4">
                  {fieldsList.map(field => (
                    <div key={field.key} className="bg-gray-50 rounded-lg p-3">
                      <dt className="text-xs text-gray-500 uppercase">{field.label}</dt>
                      <dd className="mt-1 text-sm font-medium text-gray-900">{field.value || '-'}</dd>
                    </div>
                  ))}
                </dl>
                {extractedFields.line_items && extractedFields.line_items.length > 0 && (
                  <div className="mt-6">
                    <h4 className="font-medium text-gray-900 mb-3">Chi tiết hàng hóa/dịch vụ</h4>
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">STT</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Tên</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500">SL</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500">Đơn giá</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500">Thành tiền</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {extractedFields.line_items.map((item: any, idx: number) => (
                          <tr key={idx}>
                            <td className="px-3 py-2">{idx + 1}</td>
                            <td className="px-3 py-2">{item.name}</td>
                            <td className="px-3 py-2 text-right">{item.quantity}</td>
                            <td className="px-3 py-2 text-right">{formatCurrency(item.unit_price)}</td>
                            <td className="px-3 py-2 text-right font-medium">{formatCurrency(item.amount)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {doc.extracted_text && (
                  <div className="mt-6">
                    <h4 className="font-medium text-gray-900 mb-2">Văn bản OCR</h4>
                    <pre className="text-xs text-gray-600 bg-gray-50 p-3 rounded-lg overflow-auto max-h-40 whitespace-pre-wrap">
                      {doc.extracted_text}
                    </pre>
                  </div>
                )}
              </div>
            )}

            {/* Panel C: Validation */}
            {activeTab === 'validation' && (
              <div className="space-y-4">
                <h3 className="font-medium text-gray-900">Kết quả kiểm tra</h3>
                {validationWarnings.length === 0 ? (
                  <div className="flex items-center gap-3 p-4 bg-green-50 rounded-lg">
                    <CheckCircle className="w-5 h-5 text-green-600" />
                    <p className="text-green-700">Chứng từ hợp lệ, không có cảnh báo</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {validationWarnings.map((warn, idx) => (
                      <div
                        key={idx}
                        className={`flex items-start gap-3 p-4 rounded-lg ${
                          warn.severity === 'error' ? 'bg-red-50' : 'bg-yellow-50'
                        }`}
                      >
                        {warn.severity === 'error' ? (
                          <XCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
                        ) : (
                          <AlertTriangle className="w-5 h-5 text-yellow-600 flex-shrink-0" />
                        )}
                        <p className={warn.severity === 'error' ? 'text-red-700' : 'text-yellow-700'}>
                          {warn.message}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
                <div className="mt-6 p-4 bg-blue-50 rounded-lg">
                  <div className="flex items-start gap-3">
                    <Info className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                    <div className="text-sm text-blue-700">
                      <p className="font-medium">Lưu ý</p>
                      <p className="mt-1">
                        Hệ thống tự động kiểm tra định dạng và tính đầy đủ của chứng từ.
                        Vui lòng bổ sung thông tin thiếu trước khi gửi duyệt.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Panel D: Evidence Timeline */}
            {activeTab === 'evidence' && (
              <div className="space-y-4">
                <h3 className="font-medium text-gray-900">Lịch sử xử lý</h3>
                {evidence.length === 0 ? (
                  <p className="text-gray-500 text-sm">Chưa có lịch sử xử lý</p>
                ) : (
                  <div className="relative">
                    <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-200" />
                    <div className="space-y-4">
                      {evidence.map((event: EvidenceEvent, idx: number) => (
                        <div key={event.id || idx} className="relative pl-10">
                          <div className={`absolute left-2.5 w-3 h-3 rounded-full border-2 bg-white ${
                            event.severity === 'error' ? 'border-red-500' :
                            event.severity === 'warning' ? 'border-yellow-500' :
                            event.severity === 'success' ? 'border-green-500' :
                            'border-blue-500'
                          }`} />
                          <div className="bg-gray-50 rounded-lg p-3">
                            <div className="flex items-center justify-between">
                              <span className="font-medium text-sm text-gray-900">
                                {event.step}: {event.action}
                              </span>
                              <span className="text-xs text-gray-500">
                                {formatDateTime(event.created_at || event.timestamp)}
                              </span>
                            </div>
                            {event.output_summary && (
                              <p className="mt-1 text-sm text-gray-600">{event.output_summary}</p>
                            )}
                            {event.trace_id && (
                              <p className="mt-1 text-xs text-gray-400">Trace: {event.trace_id}</p>
                            )}
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
