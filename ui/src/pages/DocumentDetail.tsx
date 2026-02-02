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
  Save,
  X,
  Settings
} from 'lucide-react';
import api from '../lib/api';
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

// ExtraFields component for managing custom fields
interface ExtraField {
  key: string;
  value: string;
}

function ExtraFieldsSection({ 
  documentId, 
  initialFields 
}: { 
  documentId: string; 
  initialFields: Record<string, any>;
}) {
  const queryClient = useQueryClient();
  const [fields, setFields] = useState<ExtraField[]>([]);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Load initial fields
  useEffect(() => {
    if (initialFields && typeof initialFields === 'object') {
      const fieldArray = Object.entries(initialFields).map(([key, value]) => ({
        key,
        value: String(value || '')
      }));
      setFields(fieldArray);
    }
  }, [initialFields]);

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: async (fieldsToSave: Record<string, string>) => {
      return api.updateExtraFields(documentId, fieldsToSave);
    },
    onSuccess: () => {
      setSaveStatus('saved');
      setErrorMessage(null);
      queryClient.invalidateQueries({ queryKey: ['document', documentId] });
      setTimeout(() => setSaveStatus('idle'), 3000);
    },
    onError: (error: any) => {
      setSaveStatus('error');
      setErrorMessage(error?.response?.data?.detail || 'Không lưu được trường bổ sung');
    }
  });

  const handleAddField = () => {
    setFields([...fields, { key: '', value: '' }]);
  };

  const handleRemoveField = (index: number) => {
    setFields(fields.filter((_, i) => i !== index));
  };

  const handleFieldChange = (index: number, field: 'key' | 'value', newValue: string) => {
    const newFields = [...fields];
    newFields[index][field] = newValue;
    setFields(newFields);
  };

  const handleSave = () => {
    // Convert array to object
    const fieldsObj: Record<string, string> = {};
    for (const f of fields) {
      if (f.key.trim()) {
        fieldsObj[f.key.trim()] = f.value;
      }
    }
    setSaveStatus('saving');
    saveMutation.mutate(fieldsObj);
  };

  return (
    <div className="bg-orange-50/50 rounded-xl p-4 border border-orange-100/50">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-bold text-orange-600 uppercase tracking-wider flex items-center gap-2">
          <Settings className="w-3 h-3" />
          TRƯỜNG BỔ SUNG
        </h3>
        <button
          onClick={handleAddField}
          className="text-xs text-orange-600 hover:text-orange-700 flex items-center gap-1 font-medium"
        >
          <Plus className="w-3 h-3" />
          Thêm trường
        </button>
      </div>

      {fields.length === 0 ? (
        <p className="text-sm text-gray-400 italic">Chưa có trường bổ sung nào</p>
      ) : (
        <div className="space-y-2">
          {fields.map((field, idx) => (
            <div key={idx} className="flex items-center gap-2">
              <input
                type="text"
                placeholder="Tên trường"
                value={field.key}
                onChange={(e) => handleFieldChange(idx, 'key', e.target.value)}
                className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
              />
              <input
                type="text"
                placeholder="Giá trị"
                value={field.value}
                onChange={(e) => handleFieldChange(idx, 'value', e.target.value)}
                className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
              />
              <button
                onClick={() => handleRemoveField(idx)}
                className="p-2 text-gray-400 hover:text-red-500 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {fields.length > 0 && (
        <div className="mt-4">
          <button
            onClick={handleSave}
            disabled={saveMutation.isPending}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-orange-500 text-white rounded-lg hover:bg-orange-600 disabled:opacity-50 transition-colors font-medium"
          >
            {saveMutation.isPending ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            Lưu trường bổ sung
          </button>
        </div>
      )}

      {/* Status messages */}
      {saveStatus === 'saved' && (
        <p className="mt-2 text-sm text-green-600 flex items-center gap-1">
          <CheckCircle2 className="w-4 h-4" />
          Đã lưu trường bổ sung.
        </p>
      )}
      {saveStatus === 'error' && (
        <p className="mt-2 text-sm text-red-600 flex items-center gap-1">
          <XCircle className="w-4 h-4" />
          {errorMessage || 'Không lưu được trường bổ sung'}
        </p>
      )}
    </div>
  );
}

export default function DocumentDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'extracted' | 'proposal' | 'ledger' | 'timeline'>('extracted');

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

  // Fetch extra fields
  const { data: extraFieldsData } = useQuery({
    queryKey: ['document-extra-fields', id],
    queryFn: () => api.getExtraFields(id!),
    enabled: !!id,
  });

  // Switch to relevant tab on status change
  useEffect(() => {
    if (doc?.status === 'proposing') setActiveTab('proposal');
    if (doc?.status === 'proposed') setActiveTab('proposal');
    if (doc?.status === 'posted') setActiveTab('ledger');
  }, [doc?.status]);

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

  // Fetch timeline
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

  const handleDelete = () => {
    if (window.confirm('Bạn có chắc chắn muốn xóa chứng từ này? Hành động này không thể hoàn tác.')) {
      deleteMutation.mutate();
    }
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
  const canPropose = ['extracted'].includes(doc.status);
  const canSubmit = ['proposed'].includes(doc.status) && proposal?.id;
  const canApprove = ['pending_approval'].includes(doc.status) && proposal?.approval_id;

  // Extracted fields - now dynamic
  const extractedFields = doc.extracted_data || doc.extracted_fields || {};

  // Field label mapping for Vietnamese UI
  const fieldLabels: Record<string, string> = {
    vendor_name: 'NHÀ CUNG CẤP',
    vendor_tax_id: 'MST',
    invoice_no: 'SỐ HÓA ĐƠN',
    invoice_number: 'SỐ HÓA ĐƠN',
    invoice_date: 'NGÀY HÓA ĐƠN',
    total_amount: 'TỔNG TIỀN',
    vat_amount: 'THUẾ VAT',
    currency: 'LOẠI TIỀN',
    description: 'NỘI DUNG',
    raw_text: 'OCR TEXT',
  };

  // Core fields to always show
  const coreFieldKeys = ['invoice_no', 'invoice_number', 'invoice_date', 'vendor_name', 'vendor_tax_id', 'total_amount', 'vat_amount', 'currency'];
  
  const coreFields = coreFieldKeys
    .filter(key => doc[key] || extractedFields[key])
    .map(key => ({
      key,
      label: fieldLabels[key] || key.toUpperCase(),
      value: key.includes('amount') 
        ? formatCurrency(doc[key] || extractedFields[key])
        : key.includes('date')
          ? formatDate(doc[key] || extractedFields[key])
          : (doc[key] || extractedFields[key] || '-')
    }));

  // Extra fields from extracted_data (excluding core fields and extra_fields)
  const extraFields = Object.entries(extractedFields)
    .filter(([key]) => !coreFieldKeys.includes(key) && key !== 'extra_fields' && key !== 'raw_text')
    .map(([key, value]) => ({
      key,
      label: fieldLabels[key] || key.replace(/_/g, ' ').toUpperCase(),
      value: typeof value === 'object' ? JSON.stringify(value) : String(value || '-')
    }));

  const displayFields = [...coreFields, ...extraFields];

  // Get saved extra fields
  const savedExtraFields = extraFieldsData?.extra_fields || extractedFields?.extra_fields || {};

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-blue-50/30 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/documents')}
            className="p-2.5 rounded-xl hover:bg-gray-100 transition-colors text-gray-500"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-xl font-bold text-gray-900 flex items-center gap-3">
              <span className="truncate max-w-md">{doc.filename}</span>
              <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${statusCfg.color}`}>
                <StatusIcon className="w-3.5 h-3.5" />
                {statusCfg.label}
              </span>
            </h1>
            <p className="text-sm text-gray-500 mt-0.5">ID: {doc.id}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {canExtract && (
            <button
              onClick={() => extractMutation.mutate()}
              disabled={extractMutation.isPending}
              className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 shadow-sm transition-all font-medium"
            >
              {extractMutation.isPending ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
              Trích xuất
            </button>
          )}
          {canPropose && (
            <button
              onClick={() => proposeMutation.mutate()}
              disabled={proposeMutation.isPending}
              className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 disabled:opacity-50 shadow-sm transition-all font-medium"
            >
              {proposeMutation.isPending ? <RefreshCw className="w-4 h-4 animate-spin" /> : <BrainCircuit className="w-4 h-4" />}
              Đề xuất
            </button>
          )}
          {canSubmit && (
            <button
              onClick={() => submitMutation.mutate(proposal.id)}
              disabled={submitMutation.isPending}
              className="flex items-center gap-2 px-4 py-2.5 bg-amber-500 text-white rounded-xl hover:bg-amber-600 disabled:opacity-50 shadow-sm transition-all font-medium"
            >
              {submitMutation.isPending ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              Gửi duyệt
            </button>
          )}
          {canApprove && (
            <button
              onClick={() => approveMutation.mutate(proposal.approval_id)}
              disabled={approveMutation.isPending}
              className="flex items-center gap-2 px-4 py-2.5 bg-green-600 text-white rounded-xl hover:bg-green-700 disabled:opacity-50 shadow-sm transition-all font-medium"
            >
              {approveMutation.isPending ? <RefreshCw className="w-4 h-4 animate-spin" /> : <ThumbsUp className="w-4 h-4" />}
              Phê duyệt
            </button>
          )}
          <button
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
            className="p-2.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-xl transition-all"
            title="Xóa chứng từ"
          >
            {deleteMutation.isPending ? <RefreshCw className="w-5 h-5 animate-spin" /> : <Trash2 className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 h-[calc(100vh-140px)]">
        {/* Left Panel: Preview */}
        <div className="bg-white rounded-2xl border border-gray-200/50 shadow-sm overflow-hidden flex flex-col h-full bg-clip-border">
          <div className="px-5 py-4 border-b flex items-center justify-between bg-gray-50/50">
            <h2 className="font-semibold text-gray-900 flex items-center gap-2">
              <Eye className="w-4 h-4 text-gray-500" />
              Preview
            </h2>
          </div>
          <div className="flex-1 bg-gray-100/50 relative overflow-hidden">
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
                <p>No preview available</p>
              </div>
            )}
          </div>
        </div>

        {/* Right Panel: Tabs & Data */}
        <div className="bg-white/90 backdrop-blur-sm rounded-2xl border border-gray-200/50 shadow-sm overflow-hidden flex flex-col h-full">
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
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${
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

          <div className="flex-1 overflow-auto p-6 scroll-smooth">
            {activeTab === 'extracted' && (
              <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                {/* Extracted Data Section */}
                <div className="bg-blue-50/50 rounded-xl p-4 border border-blue-100/50">
                  <h3 className="text-xs font-bold text-blue-600 uppercase tracking-wider mb-4 flex items-center gap-2">
                    <Zap className="w-3 h-3" />
                    DỮ LIỆU TRÍCH XUẤT
                  </h3>
                  <div className="grid grid-cols-2 gap-4">
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

                {/* Extra Fields Section - TRƯỜNG BỔ SUNG */}
                <ExtraFieldsSection 
                  documentId={doc.id} 
                  initialFields={savedExtraFields} 
                />

                {/* LLM Cleaning Results */}
                {extractedFields.cleaned_text && (
                  <div className="bg-green-50/50 rounded-xl p-4 border border-green-100/50">
                    <h3 className="text-xs font-bold text-green-600 uppercase tracking-wider mb-2 flex items-center gap-2">
                      <CheckCircle2 className="w-3 h-3" />
                      AI Cleaned Text
                    </h3>
                    <div className="max-h-40 overflow-y-auto text-xs font-mono text-gray-600 leading-relaxed bg-white p-3 rounded-lg border">
                      {extractedFields.cleaned_text}
                    </div>
                  </div>
                )}

                {/* Raw OCR Text */}
                {doc.raw_text && (
                  <div className="bg-gray-50 rounded-xl p-4 border border-gray-100">
                    <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">Raw OCR Text</h3>
                    <div className="max-h-60 overflow-y-auto text-xs font-mono text-gray-600 leading-relaxed bg-white p-3 rounded-lg border">
                      {doc.raw_text}
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'proposal' && (
              <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                {doc.status === 'proposing' ? (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <div className="relative mb-6">
                      <BrainCircuit className="w-16 h-16 text-indigo-500 animate-pulse" />
                      <div className="absolute inset-0 bg-indigo-500 rounded-full blur-xl opacity-20 animate-pulse"></div>
                    </div>
                    <h3 className="text-lg font-bold text-gray-900 mb-2">AI đang phân tích...</h3>
                    <p className="text-gray-500 max-w-xs mx-auto">Đang phân tích cấu trúc chứng từ, đối chiếu NCC, và dự đoán tài khoản.</p>
                  </div>
                ) : proposal ? (
                  <>
                    <div className="bg-gradient-to-br from-indigo-50 to-white p-5 rounded-xl border border-indigo-100 shadow-sm">
                      <div className="flex items-start gap-3">
                        <BrainCircuit className="w-5 h-5 text-indigo-600 mt-0.5" />
                        <div>
                          <h3 className="font-semibold text-indigo-900">AI Reasoning</h3>
                          <p className="text-sm text-indigo-800/80 mt-1 leading-relaxed">
                            {proposal.ai_reasoning || proposal.explanation || 'No reasoning provided.'}
                          </p>
                          <div className="mt-3 flex items-center gap-2">
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-white border border-indigo-100 text-indigo-600 shadow-sm">
                              <Zap className="w-3 h-3" />
                              Confidence: {(proposal.ai_confidence * 100).toFixed(1)}%
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
                              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Tài khoản</th>
                              <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase">Nợ</th>
                              <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase">Có</th>
                            </tr>
                          </thead>
                          <tbody className="bg-white divide-y divide-gray-100">
                            {proposal.entries?.map((entry: any, idx: number) => (
                              <tr key={idx} className="hover:bg-gray-50/50 transition-colors">
                                <td className="px-4 py-3">
                                  <div className="font-medium text-gray-900">{entry.account_code}</div>
                                  <div className="text-xs text-gray-500">{entry.account_name}</div>
                                </td>
                                <td className="px-4 py-3 text-sm text-gray-900 text-right font-medium">
                                  {entry.debit_amount || entry.debit ? formatCurrency(entry.debit_amount || entry.debit) : '-'}
                                </td>
                                <td className="px-4 py-3 text-sm text-gray-900 text-right font-medium">
                                  {entry.credit_amount || entry.credit ? formatCurrency(entry.credit_amount || entry.credit) : '-'}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                          <tfoot className="bg-gray-50 border-t border-gray-200">
                            <tr>
                              <td className="px-4 py-3 text-sm font-bold text-gray-900">Tổng</td>
                              <td className="px-4 py-3 text-sm font-bold text-gray-900 text-right text-indigo-600">
                                {formatCurrency(proposal.total_debit)}
                              </td>
                              <td className="px-4 py-3 text-sm font-bold text-gray-900 text-right text-indigo-600">
                                {formatCurrency(proposal.total_credit)}
                              </td>
                            </tr>
                          </tfoot>
                        </table>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="text-center py-12">
                    <div className="bg-indigo-50 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                      <BrainCircuit className="w-8 h-8 text-indigo-500" />
                    </div>
                    <h3 className="text-gray-900 font-medium mb-1">Chưa có đề xuất</h3>
                    <p className="text-gray-500 text-sm mb-4">Chạy bước "Đề xuất" để AI phân tích chứng từ này.</p>
                    {canPropose && (
                      <button onClick={() => proposeMutation.mutate()} className="text-indigo-600 font-medium hover:underline text-sm">
                        Chạy phân tích ngay →
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'ledger' && (
              <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                {ledger ? (
                  <div className="space-y-4">
                    <div className="bg-emerald-50 border border-emerald-100 p-4 rounded-xl flex items-center gap-4">
                      <div className="w-12 h-12 bg-white rounded-full flex items-center justify-center shadow-sm text-emerald-600">
                        <CheckCircle2 className="w-6 h-6" />
                      </div>
                      <div>
                        <h3 className="font-bold text-emerald-900">Đã ghi sổ thành công</h3>
                        <p className="text-sm text-emerald-700">
                          Bút toán <span className="font-mono font-medium">{ledger.entry_number}</span> đã được ghi nhận vào Sổ cái.
                        </p>
                      </div>
                    </div>

                    <div className="bg-white rounded-xl border overflow-hidden">
                      <div className="bg-gray-50 px-4 py-3 border-b flex justify-between">
                        <span className="font-medium text-gray-700">Chi tiết bút toán</span>
                        <span className="text-xs text-gray-500 font-mono">{formatDate(ledger.entry_date)}</span>
                      </div>
                      <div className="p-4 bg-gray-50 font-mono text-xs overflow-auto">
                        {ledger.lines ? (
                          <table className="w-full">
                            <thead className="text-left text-gray-500">
                              <tr><th>Tài khoản</th><th className="text-right">Nợ</th><th className="text-right">Có</th></tr>
                            </thead>
                            <tbody>
                              {ledger.lines.map((line: any, idx: number) => (
                                <tr key={idx} className="border-b border-gray-200 last:border-0">
                                  <td className="py-2">{line.account_code} - {line.account_name}</td>
                                  <td className="text-right">{formatCurrency(line.debit)}</td>
                                  <td className="text-right">{formatCurrency(line.credit)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        ) : (
                          <pre>{JSON.stringify(ledger, null, 2)}</pre>
                        )}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-12 text-gray-500">
                    <BookOpen className="w-12 h-12 mx-auto text-gray-300 mb-3" />
                    <p>Chưa ghi sổ.</p>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'timeline' && (
              <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                <div className="relative pl-6 border-l-2 border-gray-100 space-y-8 my-4">
                  {evidence.map((ev: any, idx: number) => (
                    <div key={idx} className="relative">
                      <span className={`absolute -left-[31px] top-0 flex h-6 w-6 items-center justify-center rounded-full ring-4 ring-white ${
                        ev.severity === 'error' ? 'bg-red-100 text-red-600' : 'bg-blue-50 text-blue-600'
                      }`}>
                        <div className={`w-2 h-2 rounded-full ${ev.severity === 'error' ? 'bg-red-500' : 'bg-blue-500'}`} />
                      </span>
                      <div>
                        <p className="text-sm font-semibold text-gray-900">{ev.step} - {ev.action}</p>
                        <p className="text-xs text-gray-500 mt-0.5">{formatDateTime(ev.timestamp)}</p>
                        {ev.output_summary && (
                          <div className="mt-2 p-3 bg-gray-50 rounded-lg text-xs text-gray-600 font-mono border border-gray-100">
                            {ev.output_summary}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                  {evidence.length === 0 && <p className="text-gray-400 italic text-sm">Chưa có hoạt động nào được ghi nhận.</p>}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
