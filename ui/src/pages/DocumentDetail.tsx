import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  FileText,
  RefreshCw,
  Zap,
  BookOpen,
  Send,
  ThumbsUp,
  Clock,
  Layout,
  BrainCircuit,
  CheckCircle2,
  XCircle,
  Eye,
  Trash2,
  Plus,
  X,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  User,
  Upload,
  Settings,
  FileCheck
} from 'lucide-react';
import api from '../lib/api';
import ModuleChatDock from '../components/moduleChat/ModuleChatDock';
import DocumentPreview from '../components/DocumentPreview';

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: any }> = {
  new: { label: 'Mới', color: 'bg-gray-100 text-gray-700', icon: FileText },
  extracting: { label: 'Đang trích xuất', color: 'bg-blue-100 text-blue-700', icon: RefreshCw },
  extracted: { label: 'Đã trích xuất', color: 'bg-cyan-100 text-cyan-700', icon: CheckCircle2 },
  proposing: { label: 'Đang suy luận (AI)', color: 'bg-purple-100 text-purple-700', icon: BrainCircuit },
  proposed: { label: 'Có đề xuất', color: 'bg-indigo-100 text-indigo-700', icon: Zap },
  pending_approval: { label: 'Chờ duyệt', color: 'bg-amber-100 text-amber-700', icon: Clock },
  approved: { label: 'Đã duyệt', color: 'bg-green-100 text-green-700', icon: CheckCircle2 },
  rejected: { label: 'Từ chối', color: 'bg-red-100 text-red-700', icon: XCircle },
  posted: { label: 'Đã ghi sổ', color: 'bg-emerald-100 text-emerald-700', icon: BookOpen },
  processed: { label: 'Đã xử lý', color: 'bg-teal-100 text-teal-700', icon: CheckCircle2 },
};

// Vietnamese labels for timeline events
const EVENT_LABELS: Record<string, string> = {
  'document.created': 'Tạo chứng từ mới',
  'document.uploaded': 'Upload file từ máy',
  'document.upload': 'Upload file',
  'ocr.started': 'Bắt đầu nhận dạng văn bản (OCR)',
  'ocr.completed': 'Hoàn thành OCR',
  'extraction.started': 'Bắt đầu trích xuất dữ liệu',
  'extraction.completed': 'Hoàn thành trích xuất',
  'proposal.started': 'Bắt đầu tạo đề xuất hạch toán',
  'proposal.created': 'Đã tạo đề xuất hạch toán',
  'proposal.completed': 'Hoàn thành đề xuất',
  'approval.submitted': 'Gửi yêu cầu duyệt',
  'approval.approved': 'Đã duyệt chứng từ',
  'approval.rejected': 'Từ chối chứng từ',
  'ledger.posted': 'Đã ghi sổ cái',
  'status.changed': 'Cập nhật trạng thái',
  'upload': 'Upload file',
  'direct': 'Tạo trực tiếp',
  'processing': 'Đang xử lý',
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

function formatTimeOnly(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
  } catch {
    return dateStr;
  }
}

// Translate event type to Vietnamese
function translateEvent(eventType: string, action?: string): string {
  const key = eventType?.toLowerCase() || action?.toLowerCase() || 'processing';
  if (EVENT_LABELS[key]) return EVENT_LABELS[key];
  
  // Fallback: try to make it readable
  return key
    .replace(/_/g, ' ')
    .replace(/\./g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase());
}

// Extract readable summary from event data
function extractEventSummary(eventData: any): string | null {
  if (!eventData) return null;
  if (typeof eventData === 'string') return eventData;
  
  // Try common fields
  const summary = eventData.summary || eventData.message || eventData.description;
  if (summary) return summary;
  
  // Try filename
  if (eventData.filename) return `File: ${eventData.filename}`;
  
  // Try status
  if (eventData.status) return `Trạng thái: ${eventData.status}`;
  
  return null;
}

export default function DocumentDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'extracted' | 'proposal' | 'ledger' | 'timeline'>('extracted');
  const [showRawTimeline, setShowRawTimeline] = useState(false);
  
  // Custom fields state
  const [customFields, setCustomFields] = useState<Array<{key: string, value: string}>>([]);
  const [showAddField, setShowAddField] = useState(false);
  const [newFieldKey, setNewFieldKey] = useState('');
  const [newFieldValue, setNewFieldValue] = useState('');
  const [customFieldsSaved, setCustomFieldsSaved] = useState(true);

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

  // Switch to relevant tab on status change
  useEffect(() => {
    if (doc?.status === 'proposing') setActiveTab('proposal');
    if (doc?.status === 'proposed') setActiveTab('proposal');
    if (doc?.status === 'posted') setActiveTab('ledger');
  }, [doc?.status]);

  // Fetch proposal (if exists)
  const { data: proposal, isLoading: loadingProposal } = useQuery({
    queryKey: ['document-proposal', id],
    queryFn: () => api.getDocumentProposal(id!),
    enabled: !!id,
    retry: false
  });

  // Fetch ledger (if posted)
  const { data: ledger } = useQuery({
    queryKey: ['document-ledger', id],
    queryFn: () => api.getDocumentLedger(id!),
    enabled: !!id && ['posted', 'approved'].includes(doc?.status),
    retry: false
  });

  // Fetch timeline/evidence
  const { data: evidence = [] } = useQuery({
    queryKey: ['document-evidence', id],
    queryFn: () => api.getDocumentEvidence(id!),
    enabled: !!id,
  });

  // Extra fields from backend (persisted)
  const { data: extraFieldsData } = useQuery({
    queryKey: ['document-extra-fields', id],
    queryFn: () => api.getExtraFields(id!),
    enabled: !!id,
  });

  // Load custom fields from backend (persisted) or document
  useEffect(() => {
    // Priority: backend saved fields > document extracted fields
    const savedFields = extraFieldsData?.extra_fields;
    const docFields = doc?.extracted_fields?.custom_fields;
    const fieldsToLoad = savedFields || docFields;
    
    if (fieldsToLoad && Object.keys(fieldsToLoad).length > 0) {
      setCustomFields(
        Object.entries(fieldsToLoad).map(([key, value]) => ({
          key,
          value: String(value)
        }))
      );
      setCustomFieldsSaved(true);
    }
  }, [extraFieldsData, doc?.extracted_fields?.custom_fields]);

  // Actions
  const extractMutation = useMutation({
    mutationFn: () => api.runExtraction(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['document', id] });
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      queryClient.invalidateQueries({ queryKey: ['document-evidence', id] });
      setActiveTab('extracted');
    },
  });

  const proposeMutation = useMutation({
    mutationFn: () => api.runProposal(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['document', id] });
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      queryClient.invalidateQueries({ queryKey: ['document-proposal', id] });
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

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteDocument(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      navigate('/documents');
    },
  });

  // Save custom fields mutation
  const saveCustomFieldsMutation = useMutation({
    mutationFn: async () => {
      // Convert array to object
      const fieldsObj: Record<string, string> = {};
      customFields.forEach(f => { if (f.key) fieldsObj[f.key] = f.value; });
      
      // Use the extra fields API to persist custom fields
      const response = await api.updateExtraFields(id!, fieldsObj);
      return response;
    },
    onSuccess: () => {
      setCustomFieldsSaved(true);
      queryClient.invalidateQueries({ queryKey: ['document', id] });
    },
    onError: (error) => {
      console.error('Failed to save custom fields:', error);
    }
  });

  const handleDelete = () => {
    if (window.confirm('Bạn có chắc chắn muốn xóa chứng từ này? Hành động này không thể hoàn tác.')) {
      deleteMutation.mutate();
    }
  };

  const handleAddCustomField = () => {
    if (newFieldKey.trim()) {
      setCustomFields([...customFields, { key: newFieldKey.trim(), value: newFieldValue }]);
      setNewFieldKey('');
      setNewFieldValue('');
      setShowAddField(false);
      setCustomFieldsSaved(false);
    }
  };

  const handleRemoveCustomField = (index: number) => {
    setCustomFields(customFields.filter((_, i) => i !== index));
    setCustomFieldsSaved(false);
  };

  const handleCustomFieldChange = (index: number, field: 'key' | 'value', value: string) => {
    const updated = [...customFields];
    updated[index][field] = value;
    setCustomFields(updated);
    setCustomFieldsSaved(false);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="flex flex-col items-center gap-4">
          <RefreshCw className="w-12 h-12 animate-spin text-blue-500" />
          <p className="text-gray-500 font-medium">Đang tải dữ liệu...</p>
        </div>
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-gray-50">
        <div className="text-center">
          <FileText className="w-16 h-16 mx-auto text-gray-300 mb-4" />
          <h2 className="text-xl font-bold text-gray-900">Không tìm thấy chứng từ</h2>
          <button onClick={() => navigate('/documents')} className="mt-4 text-blue-600 hover:underline">
            Quay lại danh sách
          </button>
        </div>
      </div>
    );
  }

  const statusCfg = STATUS_CONFIG[doc.status] || STATUS_CONFIG.new;
  const StatusIcon = statusCfg.icon;

  const canExtract = ['new', 'extracting'].includes(doc.status);
  const canPropose = ['extracted', 'processed'].includes(doc.status);
  const canSubmit = ['proposed'].includes(doc.status) && proposal?.id;
  const canApprove = ['pending_approval'].includes(doc.status) && proposal?.approval_id;

  // Extracted fields - now dynamic
  const extractedFields = doc.extracted_data || doc.extracted_fields || {};

  // Field label mapping for Vietnamese UI
  const fieldLabels: Record<string, string> = {
    invoice_no: 'Số hóa đơn',
    invoice_number: 'Số hóa đơn',
    invoice_date: 'Ngày hóa đơn',
    vendor_name: 'Nhà cung cấp',
    supplier_name: 'Nhà cung cấp',
    vendor_tax_id: 'MST NCC',
    tax_id: 'MST',
    total_amount: 'Tổng tiền',
    vat_amount: 'Thuế VAT',
    tax_amount: 'Thuế',
    currency: 'Loại tiền',
    description: 'Mô tả',
    payment_terms: 'Điều khoản thanh toán',
    due_date: 'Ngày đáo hạn',
    po_number: 'Số PO',
    bank_account: 'Số TK ngân hàng',
    bank_name: 'Ngân hàng',
    cleaned_text: 'Văn bản đã làm sạch',
  };

  // Format value based on field type
  const formatFieldValue = (key: string, value: unknown): string => {
    if (value === null || value === undefined) return '';
    if (key.includes('date')) return formatDate(value as string);
    if (key.includes('amount') || key === 'total_amount' || key === 'vat_amount') {
      return formatCurrency(value as number);
    }
    return String(value);
  };

  // Static core fields (always shown first)
  const coreFields = [
    { key: 'invoice_no', label: 'Số hóa đơn', value: doc.invoice_no || extractedFields.invoice_no || extractedFields.invoice_number },
    { key: 'invoice_date', label: 'Ngày hóa đơn', value: formatDate(doc.invoice_date || extractedFields.invoice_date) },
    { key: 'vendor_name', label: 'Nhà cung cấp', value: doc.vendor_name || extractedFields.vendor_name || extractedFields.supplier_name },
    { key: 'vendor_tax_id', label: 'MST', value: doc.vendor_tax_id || extractedFields.vendor_tax_id || extractedFields.tax_id },
    { key: 'total_amount', label: 'Tổng tiền', value: formatCurrency(doc.total_amount || extractedFields.total_amount) },
    { key: 'vat_amount', label: 'Thuế VAT', value: formatCurrency(doc.vat_amount || extractedFields.tax_amount || extractedFields.vat_amount) },
    { key: 'currency', label: 'Loại tiền', value: doc.currency || extractedFields.currency || 'VND' },
  ];

  // Dynamic extra fields from extracted_data (excluding already shown)
  const coreKeys = new Set(coreFields.map(f => f.key).concat(['invoice_number', 'supplier_name', 'tax_id', 'tax_amount', 'custom_fields']));
  const extraFields = Object.entries(extractedFields)
    .filter(([key]) => !coreKeys.has(key) && !key.startsWith('_'))
    .map(([key, value]) => ({
      key,
      label: fieldLabels[key] || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
      value: formatFieldValue(key, value),
    }));

  const displayFields = [...coreFields, ...extraFields];

  return (
    <div className="min-h-screen bg-gray-50/50 p-4 md:p-6 space-y-4">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white/80 backdrop-blur-xl p-4 rounded-2xl border border-gray-200/50 shadow-sm sticky top-0 z-10 transition-all">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/documents')}
            className="p-2 hover:bg-gray-100/80 rounded-xl transition-colors active:scale-95 duration-200"
          >
            <ArrowLeft className="w-5 h-5 text-gray-600" />
          </button>
          <div className="flex flex-col">
            <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
              {doc.filename}
              <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ${statusCfg.color} bg-opacity-10 border border-current/10`}>
                <StatusIcon className="w-3.5 h-3.5" />
                {statusCfg.label}
              </span>
            </h1>
            <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
              <Clock className="w-3.5 h-3.5" />
              <span>{formatDateTime(doc.created_at)}</span>
              <span>•</span>
              <span className="uppercase">{doc.type || doc.document_type || 'DOCUMENT'}</span>
            </div>
          </div>
        </div>

        {/* Actions Toolbar */}
        <div className="flex items-center gap-2 flex-wrap">
          {canExtract && (
            <button
              onClick={() => extractMutation.mutate()}
              disabled={extractMutation.isPending || doc.status === 'extracting'}
              className="group relative flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-blue-600 to-blue-500 text-white rounded-xl shadow-lg shadow-blue-500/20 hover:shadow-blue-500/40 transition-all hover:-translate-y-0.5 disabled:opacity-50 disabled:pointer-events-none text-sm"
            >
              {extractMutation.isPending || doc.status === 'extracting' ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Zap className="w-4 h-4 group-hover:fill-current" />
              )}
              <span className="font-medium">Trích xuất</span>
            </button>
          )}

          {canPropose && (
            <button
              onClick={() => proposeMutation.mutate()}
              disabled={proposeMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-indigo-600 to-indigo-500 text-white rounded-xl shadow-lg shadow-indigo-500/20 hover:shadow-indigo-500/40 transition-all hover:-translate-y-0.5 disabled:opacity-50 text-sm"
            >
              {proposeMutation.isPending ? <RefreshCw className="w-4 h-4 animate-spin" /> : <BrainCircuit className="w-4 h-4" />}
              <span className="font-medium">AI Đề xuất</span>
            </button>
          )}

          {canSubmit && (
            <button
              onClick={() => submitMutation.mutate(proposal.id)}
              disabled={submitMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-600 to-purple-500 text-white rounded-xl shadow-lg shadow-purple-500/20 hover:shadow-purple-500/40 transition-all hover:-translate-y-0.5 disabled:opacity-50 text-sm"
            >
              <Send className="w-4 h-4" />
              <span className="font-medium">Gửi duyệt</span>
            </button>
          )}

          {canApprove && (
            <button
              onClick={() => approveMutation.mutate(proposal.approval_id)}
              disabled={approveMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-emerald-600 to-emerald-500 text-white rounded-xl shadow-lg shadow-emerald-500/20 hover:shadow-emerald-500/40 transition-all hover:-translate-y-0.5 disabled:opacity-50 text-sm"
            >
              <ThumbsUp className="w-4 h-4" />
              <span className="font-medium">Duyệt ngay</span>
            </button>
          )}

          <div className="w-px h-8 bg-gray-200 mx-1"></div>

          <button
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
            className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-xl transition-all"
            title="Xóa chứng từ"
          >
            {deleteMutation.isPending ? <RefreshCw className="w-5 h-5 animate-spin" /> : <Trash2 className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Main Content Grid - Improved layout */}
      <div className="grid grid-cols-1 xl:grid-cols-5 gap-4 min-h-[calc(100vh-160px)]">
        {/* Left Panel: Preview - 3 columns on xl */}
        <div className="xl:col-span-3 bg-white rounded-2xl border border-gray-200/50 shadow-sm overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b flex items-center justify-between bg-gray-50/50">
            <h2 className="font-semibold text-gray-900 flex items-center gap-2">
              <Eye className="w-4 h-4 text-gray-500" />
              Preview
            </h2>
          </div>
          <div className="flex-1 bg-gray-100/50 relative overflow-auto min-h-[500px]">
            {doc.file_url ? (
              <DocumentPreview
                documentId={doc.id}
                filename={doc.filename}
                contentType={doc.content_type || 'application/pdf'}
                ocrBoxes={doc.ocr_boxes}
              />
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-gray-400">
                <FileText className="w-16 h-16 mx-auto mb-4 opacity-50" />
                <p>Không có preview</p>
              </div>
            )}
          </div>
        </div>

        {/* Right Panel: Tabs & Data - 2 columns on xl */}
        <div className="xl:col-span-2 bg-white/90 backdrop-blur-sm rounded-2xl border border-gray-200/50 shadow-sm overflow-hidden flex flex-col">
          <div className="border-b px-2">
            <nav className="flex gap-1 overflow-x-auto p-1">
              {[
                { id: 'extracted', label: 'Trích xuất', icon: Layout },
                { id: 'proposal', label: 'Đề xuất', icon: BrainCircuit },
                { id: 'ledger', label: 'Sổ cái', icon: BookOpen },
                { id: 'timeline', label: 'Timeline', icon: Clock },
              ].map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                    activeTab === tab.id
                      ? 'bg-blue-50 text-blue-700 shadow-sm ring-1 ring-blue-200'
                      : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                  }`}
                >
                  <tab.icon className={`w-4 h-4 ${activeTab === tab.id ? 'text-blue-500' : 'text-gray-400'}`} />
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          <div className="flex-1 overflow-auto p-4">
            {/* Tab: Extracted Data */}
            {activeTab === 'extracted' && (
              <div className="space-y-4">
                {/* Core Extracted Fields */}
                <div className="bg-blue-50/50 rounded-xl p-4 border border-blue-100/50">
                  <h3 className="text-xs font-bold text-blue-600 uppercase tracking-wider mb-3 flex items-center gap-2">
                    <Zap className="w-3 h-3" />
                    Dữ liệu trích xuất
                  </h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {displayFields.map(field => (
                      <div key={field.key} className="bg-white p-3 rounded-lg border border-gray-100 shadow-sm">
                        <dt className="text-xs text-gray-500 uppercase font-medium">{field.label}</dt>
                        <dd className="mt-1 text-sm font-semibold text-gray-900 truncate" title={String(field.value)}>
                          {field.value || <span className="text-gray-300 italic">Trống</span>}
                        </dd>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Custom Fields Section */}
                <div className="bg-amber-50/50 rounded-xl p-4 border border-amber-100/50">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-xs font-bold text-amber-600 uppercase tracking-wider flex items-center gap-2">
                      <Settings className="w-3 h-3" />
                      Trường bổ sung
                    </h3>
                    <button
                      onClick={() => setShowAddField(true)}
                      className="flex items-center gap-1 text-xs text-amber-700 hover:text-amber-800 font-medium"
                    >
                      <Plus className="w-3 h-3" />
                      Thêm trường
                    </button>
                  </div>

                  {/* Add Field Form */}
                  {showAddField && (
                    <div className="bg-white p-3 rounded-lg border border-amber-200 mb-3 space-y-2">
                      <input
                        type="text"
                        placeholder="Tên trường (vd: Mã hợp đồng)"
                        value={newFieldKey}
                        onChange={(e) => setNewFieldKey(e.target.value)}
                        className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-amber-500"
                      />
                      <input
                        type="text"
                        placeholder="Giá trị"
                        value={newFieldValue}
                        onChange={(e) => setNewFieldValue(e.target.value)}
                        className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-amber-500"
                      />
                      <div className="flex gap-2">
                        <button
                          onClick={handleAddCustomField}
                          className="flex-1 px-3 py-1.5 bg-amber-600 text-white rounded-lg text-sm font-medium hover:bg-amber-700"
                        >
                          Thêm
                        </button>
                        <button
                          onClick={() => { setShowAddField(false); setNewFieldKey(''); setNewFieldValue(''); }}
                          className="px-3 py-1.5 text-gray-600 hover:bg-gray-100 rounded-lg text-sm"
                        >
                          Hủy
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Custom Fields List */}
                  {customFields.length > 0 ? (
                    <div className="space-y-2">
                      {customFields.map((field, idx) => (
                        <div key={idx} className="bg-white p-3 rounded-lg border border-gray-100 flex items-center gap-2">
                          <div className="flex-1 grid grid-cols-2 gap-2">
                            <input
                              type="text"
                              value={field.key}
                              onChange={(e) => handleCustomFieldChange(idx, 'key', e.target.value)}
                              className="px-2 py-1 border rounded text-sm"
                              placeholder="Tên trường"
                            />
                            <input
                              type="text"
                              value={field.value}
                              onChange={(e) => handleCustomFieldChange(idx, 'value', e.target.value)}
                              className="px-2 py-1 border rounded text-sm"
                              placeholder="Giá trị"
                            />
                          </div>
                          <button
                            onClick={() => handleRemoveCustomField(idx)}
                            className="p-1 text-gray-400 hover:text-red-500"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      ))}
                      
                      {/* Save button */}
                      {!customFieldsSaved && (
                        <button
                          onClick={() => saveCustomFieldsMutation.mutate()}
                          disabled={saveCustomFieldsMutation.isPending}
                          className="w-full mt-2 px-4 py-2 bg-amber-600 text-white rounded-lg text-sm font-medium hover:bg-amber-700 disabled:opacity-50 flex items-center justify-center gap-2"
                        >
                          {saveCustomFieldsMutation.isPending ? (
                            <RefreshCw className="w-4 h-4 animate-spin" />
                          ) : (
                            <CheckCircle2 className="w-4 h-4" />
                          )}
                          Lưu trường bổ sung
                        </button>
                      )}
                      
                      {saveCustomFieldsMutation.isError && (
                        <p className="text-xs text-red-600 mt-1">
                          Chưa thể lưu trường bổ sung. Dữ liệu được giữ trong phiên làm việc.
                        </p>
                      )}
                    </div>
                  ) : (
                    <p className="text-sm text-amber-700/70 italic">
                      Chưa có trường bổ sung. Bấm "Thêm trường" để thêm mới.
                    </p>
                  )}
                </div>

                {/* Raw Text */}
                {(extractedFields.cleaned_text || doc.raw_text || doc.extracted_text) && (
                  <div className="bg-gray-50 rounded-xl p-4 border border-gray-100">
                    <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">Văn bản OCR</h3>
                    <div className="max-h-40 overflow-y-auto text-xs font-mono text-gray-600 leading-relaxed bg-white p-3 rounded-lg border">
                      {extractedFields.cleaned_text || doc.raw_text || doc.extracted_text}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Tab: Proposal */}
            {activeTab === 'proposal' && (
              <div className="space-y-4">
                {doc.status === 'proposing' ? (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <div className="relative mb-6">
                      <BrainCircuit className="w-16 h-16 text-indigo-500 animate-pulse" />
                      <div className="absolute inset-0 bg-indigo-500 rounded-full blur-xl opacity-20 animate-pulse"></div>
                    </div>
                    <h3 className="text-lg font-bold text-gray-900 mb-2">AI đang phân tích...</h3>
                    <p className="text-gray-500 max-w-xs mx-auto text-sm">
                      Đang phân tích cấu trúc chứng từ, đối chiếu nhà cung cấp và dự đoán tài khoản hạch toán.
                    </p>
                  </div>
                ) : proposal ? (
                  <>
                    <div className="bg-gradient-to-br from-indigo-50 to-white p-4 rounded-xl border border-indigo-100 shadow-sm">
                      <div className="flex items-start gap-3">
                        <BrainCircuit className="w-5 h-5 text-indigo-600 mt-0.5" />
                        <div>
                          <h3 className="font-semibold text-indigo-900">AI Reasoning</h3>
                          <p className="text-sm text-indigo-800/80 mt-1 leading-relaxed">
                            {proposal.ai_reasoning || proposal.reasoning || proposal.explanation || 'Không có diễn giải.'}
                          </p>
                          <div className="mt-3 flex items-center gap-2">
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-white border border-indigo-100 text-indigo-600 shadow-sm">
                              <Zap className="w-3 h-3" />
                              Confidence: {((proposal.ai_confidence || 0) * 100).toFixed(1)}%
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div>
                      <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                        <BookOpen className="w-4 h-4 text-gray-500" />
                        Bút toán đề xuất
                      </h3>
                      <div className="border border-gray-200 rounded-xl overflow-hidden shadow-sm">
                        <table className="min-w-full divide-y divide-gray-200">
                          <thead className="bg-gray-50/80">
                            <tr>
                              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Tài khoản</th>
                              <th className="px-3 py-2 text-right text-xs font-semibold text-gray-500 uppercase">Nợ</th>
                              <th className="px-3 py-2 text-right text-xs font-semibold text-gray-500 uppercase">Có</th>
                            </tr>
                          </thead>
                          <tbody className="bg-white divide-y divide-gray-100">
                            {proposal.entries?.map((entry: any, idx: number) => (
                              <tr key={idx} className="hover:bg-gray-50/50 transition-colors">
                                <td className="px-3 py-2">
                                  <div className="font-medium text-gray-900 text-sm">{entry.account_code}</div>
                                  <div className="text-xs text-gray-500">{entry.account_name || entry.description}</div>
                                </td>
                                <td className="px-3 py-2 text-sm text-gray-900 text-right font-medium">
                                  {entry.debit_amount || entry.debit ? formatCurrency(entry.debit_amount || entry.debit) : '-'}
                                </td>
                                <td className="px-3 py-2 text-sm text-gray-900 text-right font-medium">
                                  {entry.credit_amount || entry.credit ? formatCurrency(entry.credit_amount || entry.credit) : '-'}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                          <tfoot className="bg-gray-50 border-t border-gray-200">
                            <tr>
                              <td className="px-3 py-2 text-sm font-bold text-gray-900">Tổng cộng</td>
                              <td className="px-3 py-2 text-sm font-bold text-indigo-600 text-right">
                                {formatCurrency(proposal.total_debit)}
                              </td>
                              <td className="px-3 py-2 text-sm font-bold text-indigo-600 text-right">
                                {formatCurrency(proposal.total_credit)}
                              </td>
                            </tr>
                          </tfoot>
                        </table>
                      </div>
                    </div>

                    {/* Re-run proposal button */}
                    <button
                      onClick={() => proposeMutation.mutate()}
                      disabled={proposeMutation.isPending}
                      className="flex items-center gap-2 px-4 py-2 text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50 text-sm font-medium"
                    >
                      <RefreshCw className={`w-4 h-4 ${proposeMutation.isPending ? 'animate-spin' : ''}`} />
                      Chạy lại đề xuất
                    </button>
                  </>
                ) : (
                  <div className="text-center py-12">
                    <div className="bg-indigo-50 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                      <BrainCircuit className="w-8 h-8 text-indigo-500" />
                    </div>
                    <h3 className="text-gray-900 font-medium mb-1">Chưa có đề xuất</h3>
                    <p className="text-gray-500 text-sm mb-4">
                      Bấm "Tạo đề xuất" để AI phân tích chứng từ này.
                    </p>
                    <button
                      onClick={() => proposeMutation.mutate()}
                      disabled={proposeMutation.isPending || loadingProposal}
                      className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-indigo-600 to-indigo-500 text-white rounded-xl shadow-lg shadow-indigo-500/20 hover:shadow-indigo-500/40 transition-all disabled:opacity-50"
                    >
                      {proposeMutation.isPending ? (
                        <RefreshCw className="w-4 h-4 animate-spin" />
                      ) : (
                        <BrainCircuit className="w-4 h-4" />
                      )}
                      <span className="font-medium">Tạo đề xuất</span>
                    </button>
                    
                    {proposeMutation.isError && (
                      <div className="mt-4 p-3 bg-red-50 border border-red-100 rounded-lg text-sm text-red-700 flex items-center gap-2">
                        <AlertCircle className="w-4 h-4" />
                        Không tạo được đề xuất. Vui lòng thử lại hoặc kiểm tra chứng từ.
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Tab: Ledger */}
            {activeTab === 'ledger' && (
              <div className="space-y-4">
                {ledger && ledger.posted ? (
                  <div className="space-y-4">
                    <div className="bg-emerald-50 border border-emerald-100 p-4 rounded-xl flex items-center gap-4">
                      <div className="w-12 h-12 bg-white rounded-full flex items-center justify-center shadow-sm text-emerald-600">
                        <CheckCircle2 className="w-6 h-6" />
                      </div>
                      <div>
                        <h3 className="font-bold text-emerald-900">Đã ghi sổ thành công</h3>
                        <p className="text-sm text-emerald-700">
                          Bút toán <span className="font-mono font-medium">{ledger.id?.substring(0, 8)}</span> đã được ghi nhận vào sổ cái.
                        </p>
                      </div>
                    </div>

                    <div className="bg-white rounded-xl border overflow-hidden">
                      <div className="bg-gray-50 px-4 py-3 border-b flex justify-between">
                        <span className="font-medium text-gray-700">Chi tiết bút toán</span>
                        <span className="text-xs text-gray-500 font-mono">{formatDate(ledger.entry_date)}</span>
                      </div>
                      <div className="p-4">
                        {ledger.lines && ledger.lines.length > 0 ? (
                          <table className="w-full text-sm">
                            <thead className="text-left text-gray-500 text-xs uppercase">
                              <tr>
                                <th className="pb-2">Tài khoản</th>
                                <th className="text-right pb-2">Nợ</th>
                                <th className="text-right pb-2">Có</th>
                              </tr>
                            </thead>
                            <tbody>
                              {ledger.lines.map((line: any, idx: number) => (
                                <tr key={idx} className="border-b border-gray-100 last:border-0">
                                  <td className="py-2">
                                    <span className="font-medium">{line.account_code}</span>
                                    {line.account_name && <span className="text-gray-500 ml-1">- {line.account_name}</span>}
                                  </td>
                                  <td className="text-right">{formatCurrency(line.debit)}</td>
                                  <td className="text-right">{formatCurrency(line.credit)}</td>
                                </tr>
                              ))}
                            </tbody>
                            <tfoot className="font-bold border-t">
                              <tr>
                                <td className="pt-2">Tổng</td>
                                <td className="text-right pt-2">{formatCurrency(ledger.total_debit)}</td>
                                <td className="text-right pt-2">{formatCurrency(ledger.total_credit)}</td>
                              </tr>
                            </tfoot>
                          </table>
                        ) : (
                          <pre className="text-xs font-mono text-gray-600 overflow-auto">{JSON.stringify(ledger, null, 2)}</pre>
                        )}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-12 text-gray-500">
                    <div className="bg-gray-100 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                      <BookOpen className="w-8 h-8 text-gray-400" />
                    </div>
                    <h3 className="font-medium text-gray-900 mb-1">Chưa ghi sổ</h3>
                    <p className="text-sm">Chứng từ này chưa được ghi nhận vào sổ cái.</p>
                    <p className="text-xs text-gray-400 mt-2">
                      Cần duyệt chứng từ trước khi ghi sổ.
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Tab: Timeline - Improved */}
            {activeTab === 'timeline' && (
              <div className="space-y-4">
                {/* Toggle for raw JSON */}
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-gray-700">Lịch sử xử lý</h3>
                  <button
                    onClick={() => setShowRawTimeline(!showRawTimeline)}
                    className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700"
                  >
                    {showRawTimeline ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                    {showRawTimeline ? 'Ẩn JSON' : 'Xem JSON thô'}
                  </button>
                </div>

                {/* Timeline List */}
                <div className="relative pl-6 border-l-2 border-gray-200 space-y-4">
                  {evidence.length > 0 ? (
                    evidence.map((ev: any, idx: number) => {
                      const eventLabel = translateEvent(ev.event_type || ev.step, ev.action);
                      const summary = extractEventSummary(ev.event_data || ev.output_summary);
                      const isError = ev.severity === 'error' || ev.event_type?.includes('error');
                      
                      return (
                        <div key={idx} className="relative">
                          <span className={`absolute -left-[25px] top-0 flex h-4 w-4 items-center justify-center rounded-full ring-4 ring-white ${
                            isError ? 'bg-red-100' : 'bg-blue-100'
                          }`}>
                            <div className={`w-2 h-2 rounded-full ${isError ? 'bg-red-500' : 'bg-blue-500'}`} />
                          </span>
                          <div className="bg-white p-3 rounded-lg border border-gray-100 shadow-sm">
                            <div className="flex items-center justify-between">
                              <p className="text-sm font-medium text-gray-900 flex items-center gap-2">
                                {isError ? (
                                  <AlertCircle className="w-3.5 h-3.5 text-red-500" />
                                ) : idx === 0 ? (
                                  <Upload className="w-3.5 h-3.5 text-blue-500" />
                                ) : (
                                  <FileCheck className="w-3.5 h-3.5 text-green-500" />
                                )}
                                {eventLabel}
                              </p>
                              <span className="text-xs text-gray-400">
                                {formatTimeOnly(ev.timestamp || ev.created_at)}
                              </span>
                            </div>
                            {summary && (
                              <p className="text-xs text-gray-600 mt-1 pl-5">
                                {summary}
                              </p>
                            )}
                            {ev.actor && (
                              <p className="text-xs text-gray-400 mt-1 pl-5 flex items-center gap-1">
                                <User className="w-3 h-3" />
                                {ev.actor}
                              </p>
                            )}
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <div className="text-center py-8 text-gray-500">
                      <Clock className="w-8 h-8 mx-auto text-gray-300 mb-2" />
                      <p className="text-sm">Chưa có hoạt động nào được ghi nhận.</p>
                    </div>
                  )}
                </div>

                {/* Raw JSON (collapsible) */}
                {showRawTimeline && evidence.length > 0 && (
                  <div className="bg-gray-50 rounded-lg p-3 border">
                    <h4 className="text-xs font-medium text-gray-500 mb-2">JSON thô (debug)</h4>
                    <pre className="text-xs font-mono text-gray-600 overflow-auto max-h-60">
                      {JSON.stringify(evidence, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
      <ModuleChatDock module="documents" scope={{ document_id: id }} />
    </div>
  );
}
