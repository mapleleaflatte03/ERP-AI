import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
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

// Mock data for demo when API is not available
const MOCK_DOCUMENTS: Document[] = [
  {
    id: 'doc-001',
    filename: 'hoadon_vpp_01.pdf',
    type: 'invoice',
    status: 'proposed',
    vendor_name: 'Công ty TNHH Văn Phòng Phẩm ABC',
    invoice_no: 'HD-2024-001234',
    invoice_date: '2026-01-15',
    total_amount: 11000000,
    vat_amount: 1000000,
    created_at: '2026-01-23T10:30:00Z',
    updated_at: '2026-01-23T11:00:00Z',
  },
  {
    id: 'doc-002',
    filename: 'sao_ke_vietcombank_t12.xlsx',
    type: 'bank_statement',
    status: 'extracted',
    created_at: '2026-01-22T09:00:00Z',
    updated_at: '2026-01-22T10:30:00Z',
  },
  {
    id: 'doc-003',
    filename: 'phieu_chi_pc2026_045.pdf',
    type: 'payment_voucher',
    status: 'pending_approval',
    vendor_name: 'Nhà cung cấp XYZ',
    total_amount: 5500000,
    created_at: '2026-01-21T14:00:00Z',
    updated_at: '2026-01-21T15:00:00Z',
  },
  {
    id: 'doc-004',
    filename: 'invoice_dien_evn_01.pdf',
    type: 'invoice',
    status: 'approved',
    vendor_name: 'Điện lực EVN',
    invoice_no: 'EVN-2026-0045',
    total_amount: 3200000,
    vat_amount: 320000,
    created_at: '2026-01-20T08:00:00Z',
    updated_at: '2026-01-20T11:00:00Z',
  },
  {
    id: 'doc-005',
    filename: 'hop_dong_thue_van_phong.pdf',
    type: 'contract',
    status: 'new',
    created_at: '2026-01-23T08:00:00Z',
    updated_at: '2026-01-23T08:00:00Z',
  },
];

export default function DocumentsInbox() {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<DocumentStatus | ''>('');
  const [typeFilter, setTypeFilter] = useState<DocumentType | ''>('');
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);

  // Use mock data for demo, try API first
  const { data: documents = MOCK_DOCUMENTS, isLoading, error } = useQuery<Document[]>({
    queryKey: ['documents', statusFilter],
    queryFn: async () => {
      try {
        return await api.getDocuments(statusFilter || undefined);
      } catch {
        return MOCK_DOCUMENTS;
      }
    },
  });

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
      for (const file of files) {
        await api.uploadDocument(file);
      }
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
      for (const file of files) {
        await api.uploadDocument(file);
      }
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

      {/* Upload Area */}
      <div
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-colors ${
          isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
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
              <div className="text-2xl font-bold">{documents?.filter(d => d.status === 'pending_approval').length || 0}</div>
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
              <div className="text-2xl font-bold">{documents?.filter(d => d.status === 'approved' || d.status === 'posted').length || 0}</div>
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
              <div className="text-2xl font-bold">{documents?.filter(d => d.status === 'rejected').length || 0}</div>
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
