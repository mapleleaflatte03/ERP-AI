import { useState, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  Upload,
  FileText,
  Search,
  ChevronRight,
  AlertCircle,
  Loader2,
  CheckCircle2,
  Clock,
  XCircle,
  Eye,
  Receipt,
  CreditCard,
  Wallet,
  FolderOpen,
} from 'lucide-react';
import api from '../lib/api';
import type { Document, DocumentStatus, DocumentType } from '../types';

const STATUS_LABELS: Record<DocumentStatus, string> = {
  new: 'Mới',
  extracting: 'Đang trích xuất',
  extracted: 'Đã trích xuất',
  proposing: 'Đang đề xuất',
  proposed: 'Có đề xuất',
  pending_approval: 'Chờ duyệt',
  approved: 'Đã duyệt',
  rejected: 'Từ chối',
  posted: 'Đã ghi sổ',
};

const STATUS_COLORS: Record<DocumentStatus, string> = {
  new: 'bg-gray-100 text-gray-700',
  extracting: 'bg-blue-100 text-blue-700',
  extracted: 'bg-blue-100 text-blue-700',
  proposing: 'bg-amber-100 text-amber-700',
  proposed: 'bg-purple-100 text-purple-700',
  pending_approval: 'bg-amber-100 text-amber-700',
  approved: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
  posted: 'bg-teal-100 text-teal-700',
};

const TYPE_LABELS: Record<DocumentType, string> = {
  invoice: 'Hóa đơn',
  receipt: 'Phiếu thu',
  bank_statement: 'Sổ phụ NH',
  contract: 'Hợp đồng',
  payment_voucher: 'Phiếu chi',
  other: 'Khác',
};

function formatCurrency(amount?: number): string {
  if (!amount) return '-';
  return new Intl.NumberFormat('vi-VN').format(amount) + ' VND';
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('vi-VN');
}



export default function DocumentsInbox() {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<DocumentStatus | ''>('');
  const [typeFilter, setTypeFilter] = useState<DocumentType | ''>('');
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);

  // Fetch documents from real backend API only
  const { data: documents = [], isLoading, error } = useQuery<Document[]>({
    queryKey: ['documents', statusFilter, typeFilter],
    queryFn: async () => {
      try {
        const params: Record<string, string> = {};
        if (statusFilter) params.status = statusFilter;
        if (typeFilter) params.type = typeFilter;
        const response = await api.getDocuments(params);
        // API returns { documents: [], total: ... } but component expects Document[]
        return Array.isArray(response) ? response : (response.documents || []);
      } catch (err) {
        console.error("Failed to fetch documents:", err);
        return [];
      }
    },
  });

  // Calculate stats in one pass
  const stats = useMemo(() => {
    return (documents || []).reduce(
      (acc, doc) => {
        if (doc.status === 'pending_approval') acc.pending++;
        else if (doc.status === 'approved' || doc.status === 'posted') acc.approved++;
        else if (doc.status === 'rejected') acc.rejected++;
        return acc;
      },
      { pending: 0, approved: 0, rejected: 0 }
    );
  }, [documents]);

  // Filter documents
  const filteredDocuments = useMemo(() => {
    return (documents || []).filter(doc => {
      if (statusFilter && doc.status !== statusFilter) return false;
      if (typeFilter && doc.type !== typeFilter) return false;
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        return (
          doc.filename.toLowerCase().includes(query) ||
          doc.vendor_name?.toLowerCase().includes(query) ||
          doc.invoice_no?.toLowerCase().includes(query)
        );
      }
      return true;
    });
  }, [documents, statusFilter, typeFilter, searchQuery]);

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    if (files.length === 0) return;

    setUploading(true);
    try {
      await Promise.all(files.map(file => api.uploadDocument(file)));
      // Invalidate queries to refresh list immediately
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    } catch (err) {
      console.error('Upload failed:', err);
    }
    setUploading(false);
  };

  const handleFileInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    setUploading(true);
    try {
      await Promise.all(files.map(file => api.uploadDocument(file)));
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    } catch (err) {
      console.error('Upload failed:', err);
    }
    setUploading(false);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Inbox Chứng từ</h1>
          <p className="text-gray-500 text-sm mt-1">Quản lý hóa đơn, phiếu thu/chi, và chứng từ kế toán</p>
        </div>
      </div>

      {/* Document Type Tabs */}
      <div className="flex gap-2 overflow-x-auto pb-2">
        {[
          { value: '', label: 'Tất cả', icon: FolderOpen },
          { value: 'invoice', label: 'Hóa đơn', icon: Receipt },
          { value: 'receipt', label: 'Phiếu thu', icon: Wallet },
          { value: 'payment_voucher', label: 'Phiếu chi', icon: CreditCard },
          { value: 'bank_statement', label: 'Sổ phụ NH', icon: FileText },
          { value: 'other', label: 'Khác', icon: FileText },
        ].map(tab => (
          <button
            key={tab.value}
            onClick={() => setTypeFilter(tab.value as DocumentType | '')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${typeFilter === tab.value
              ? 'bg-blue-600 text-white'
              : 'bg-white border hover:bg-gray-50 text-gray-700'
              }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Upload Area */}
      <div
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-colors ${isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
          }`}
      >
        <input
          type="file"
          id="file-upload"
          className="hidden"
          multiple
          accept=".pdf,.png,.jpg,.jpeg,.xlsx,.xls"
          onChange={handleFileInput}
        />
        <label htmlFor="file-upload" className="cursor-pointer">
          <div className="flex flex-col items-center gap-3">
            {uploading ? (
              <Loader2 className="w-10 h-10 text-blue-500 animate-spin" />
            ) : (
              <Upload className="w-10 h-10 text-gray-400" />
            )}
            <div>
              <p className="text-gray-700 font-medium">
                {uploading ? 'Đang tải lên...' : 'Kéo thả chứng từ vào đây'}
              </p>
              <p className="text-gray-500 text-sm mt-1">
                hoặc <span className="text-blue-600 hover:text-blue-700">chọn file</span> từ máy tính
              </p>
            </div>
            <p className="text-xs text-gray-400">Hỗ trợ: PDF, PNG, JPG, XLSX (tối đa 10MB)</p>
          </div>
        </label>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 items-center">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Tìm theo tên file, NCC, số hóa đơn..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value as DocumentStatus | '')}
          className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Tất cả trạng thái</option>
          {Object.entries(STATUS_LABELS).map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>
        <select
          value={typeFilter}
          onChange={e => setTypeFilter(e.target.value as DocumentType | '')}
          className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Tất cả loại</option>
          {Object.entries(TYPE_LABELS).map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>
      </div>

      {/* Stats Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center">
              <FileText className="w-5 h-5 text-gray-600" />
            </div>
            <div>
              <div className="text-2xl font-bold">{documents?.length || 0}</div>
              <div className="text-sm text-gray-500">Tổng chứng từ</div>
            </div>
          </div>
        </div>
        <div className="bg-white p-4 rounded-xl border">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">
              <Clock className="w-5 h-5 text-amber-600" />
            </div>
            <div>
              <div className="text-2xl font-bold">{stats.pending}</div>
              <div className="text-sm text-gray-500">Chờ duyệt</div>
            </div>
          </div>
        </div>
        <div className="bg-white p-4 rounded-xl border">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <CheckCircle2 className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <div className="text-2xl font-bold">{stats.approved}</div>
              <div className="text-sm text-gray-500">Đã duyệt</div>
            </div>
          </div>
        </div>
        <div className="bg-white p-4 rounded-xl border">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
              <XCircle className="w-5 h-5 text-red-600" />
            </div>
            <div>
              <div className="text-2xl font-bold">{stats.rejected}</div>
              <div className="text-sm text-gray-500">Từ chối</div>
            </div>
          </div>
        </div>
      </div>

      {/* Documents List */}
      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center">
            <Loader2 className="w-8 h-8 animate-spin mx-auto text-blue-500" />
            <p className="text-gray-500 mt-2">Đang tải danh sách chứng từ...</p>
          </div>
        ) : error ? (
          <div className="p-8 text-center">
            <AlertCircle className="w-8 h-8 mx-auto text-red-500" />
            <p className="text-red-600 mt-2">Không thể tải danh sách</p>
          </div>
        ) : filteredDocuments.length === 0 ? (
          <div className="p-8 text-center">
            <FileText className="w-12 h-12 mx-auto text-gray-300" />
            <p className="text-gray-500 mt-2">Chưa có chứng từ nào</p>
            <p className="text-gray-400 text-sm">Tải lên chứng từ đầu tiên của bạn</p>
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tên file</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Loại</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">NCC / Khách hàng</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Số tiền</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Trạng thái</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Ngày tạo</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {filteredDocuments.map(doc => (
                <tr key={doc.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-gray-400 flex-shrink-0" />
                      <span className="font-medium text-gray-900 truncate max-w-[200px]">{doc.filename}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {TYPE_LABELS[doc.type] || doc.type}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-600 truncate max-w-[200px]">
                    {doc.vendor_name || '-'}
                  </td>
                  <td className="px-4 py-3 text-sm text-right text-gray-900 font-medium">
                    {formatCurrency(doc.total_amount)}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${STATUS_COLORS[doc.status]}`}>
                      {STATUS_LABELS[doc.status]}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {formatDate(doc.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      to={`/documents/${doc.id}`}
                      className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800"
                    >
                      <Eye className="w-4 h-4" />
                      Xem
                      <ChevronRight className="w-4 h-4" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
