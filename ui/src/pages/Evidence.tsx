import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  Clock,
  FileText,
  User,
  CheckCircle2,
  XCircle,
  ChevronRight,
  Search,
  ArrowLeft,
  FileCheck,
  Edit3,
  Upload,
  Brain,
  Bookmark,
  Shield,
  Activity,
} from 'lucide-react';
import api from '../lib/api';
import type { EvidenceEvent } from '../types';
import ModuleChatDock from '../components/moduleChat/ModuleChatDock';


const ACTION_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  'document.uploaded': Upload,
  'document.posted': Bookmark,
  'extraction.started': Brain,
  'extraction.completed': FileCheck,
  'journal.proposed': Edit3,
  'journal.approved': CheckCircle2,
  'journal.rejected': XCircle,
};

const ACTION_COLORS: Record<string, string> = {
  'document.uploaded': 'text-blue-600 bg-blue-50 border-blue-200',
  'document.posted': 'text-green-600 bg-green-50 border-green-200',
  'extraction.started': 'text-purple-600 bg-purple-50 border-purple-200',
  'extraction.completed': 'text-purple-600 bg-purple-50 border-purple-200',
  'journal.proposed': 'text-amber-600 bg-amber-50 border-amber-200',
  'journal.approved': 'text-green-600 bg-green-50 border-green-200',
  'journal.rejected': 'text-red-600 bg-red-50 border-red-200',
};

const ACTION_LABELS: Record<string, string> = {
  'document.uploaded': 'Tải lên chứng từ',
  'document.posted': 'Ghi sổ cái',
  'extraction.started': 'Bắt đầu trích xuất',
  'extraction.completed': 'Hoàn tất trích xuất',
  'journal.proposed': 'Đề xuất hạch toán',
  'journal.approved': 'Duyệt bút toán',
  'journal.rejected': 'Từ chối bút toán',
};

function formatTimestamp(ts: string): string {
  const date = new Date(ts);
  return date.toLocaleString('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function formatRelativeTime(ts: string): string {
  const now = new Date();
  const date = new Date(ts);
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);

  if (diffMin < 1) return 'Vừa xong';
  if (diffMin < 60) return `${diffMin} phút trước`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour} giờ trước`;
  const diffDay = Math.floor(diffHour / 24);
  return `${diffDay} ngày trước`;
}

function getActorLabel(actor: string): string {
  if (actor.startsWith('user:')) {
    return actor.replace('user:', '');
  }
  if (actor.startsWith('agent:')) {
    const name = actor.replace('agent:', '');
    const labels: Record<string, string> = {
      'ocr-extractor': 'AI OCR Extractor',
      'accounting-agent': 'AI Kế toán',
    };
    return labels[name] || name;
  }
  return actor;
}

function EventCard({ event }: { event: EvidenceEvent }) {
  const Icon = ACTION_ICONS[event.action] || FileText;
  const colorClass = ACTION_COLORS[event.action] || 'text-gray-600 bg-gray-50 border-gray-200';
  const label = ACTION_LABELS[event.action] || event.action;

  return (
    <div className="quantum-card flex gap-4 p-4 hover:shadow-sm transition-shadow">
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center border ${colorClass}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h4 className="font-medium text-gray-900">{label}</h4>
            <p className="text-sm text-gray-500 mt-0.5">
              <span className="inline-flex items-center gap-1">
                <User className="w-3 h-3" />
                {getActorLabel(event.actor)}
              </span>
            </p>
          </div>
          <div className="text-right flex-shrink-0">
            <p className="text-xs text-gray-400">{formatRelativeTime(event.timestamp)}</p>
            <p className="text-xs text-gray-500 mt-0.5">{formatTimestamp(event.timestamp)}</p>
          </div>
        </div>

        {/* Payload details */}
        {event.payload && Object.keys(event.payload).length > 0 && (
          <div className="mt-2 p-2 bg-gray-50 rounded text-xs font-mono text-gray-600 space-y-1">
            {Object.entries(event.payload).map(([key, value]) => (
              <div key={key} className="flex gap-2">
                <span className="text-gray-400">{key}:</span>
                <span className="text-gray-700">{JSON.stringify(value)}</span>
              </div>
            ))}
          </div>
        )}

        {/* Document link */}
        <Link
          to={`/documents/${event.document_id}`}
          className="mt-2 inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800"
        >
          <FileText className="w-3 h-3" />
          {event.document_id}
          <ChevronRight className="w-3 h-3" />
        </Link>
      </div>
    </div>
  );
}

export default function Evidence() {
  const { documentId } = useParams();
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [filterAction, setFilterAction] = useState<string>('all');

  // Fetch summary stats (system-wide)
  const { data: summaryData } = useQuery({
    queryKey: ['evidence-summary'],
    queryFn: () => api.getEvidence(),
    enabled: !documentId, // Only fetch if not looking at specific document
  });

  // Fetch timeline events
  const { data: eventsWrapper, isLoading } = useQuery<{ events: EvidenceEvent[] } | EvidenceEvent[]>({
    queryKey: ['evidence-events', documentId],
    queryFn: async () => {
      if (documentId) {
        return api.getDocumentEvidence(documentId);
      }
      return api.getGlobalTimeline();
    },
  });

  // Normalize events data (backend might return array or { events: [...] })
  const events: EvidenceEvent[] = Array.isArray(eventsWrapper)
    ? eventsWrapper
    : (eventsWrapper?.events || []);

  const filteredEvents = events.filter(evt => {
    if (filterAction !== 'all' && evt.action !== filterAction) return false;
    if (searchQuery) {
      const searchLower = searchQuery.toLowerCase();
      return (
        evt.action.toLowerCase().includes(searchLower) ||
        evt.actor.toLowerCase().includes(searchLower) ||
        (evt.document_id && evt.document_id.toLowerCase().includes(searchLower))
      );
    }
    return true;
  });

  const metrics = summaryData?.metrics || {};

  return (
    <div className="space-y-6">
      {/* Quantum Header */}
      <div className="quantum-header">
        <div className="flex items-center gap-4">
          {documentId && (
            <button
              onClick={() => navigate(-1)}
              className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
          )}
          <div className="quantum-header__icon">
            <Shield className="w-6 h-6" />
          </div>
          <div>
            <h1 className="quantum-header__title">
              {documentId ? `Lịch sử: ${documentId.slice(0, 8)}...` : 'Nhật ký hoạt động'}
            </h1>
            <p className="quantum-header__subtitle">
              {documentId ? 'Timeline đầy đủ các sự kiện' : 'Audit trail & Evidence store'}
            </p>
          </div>
        </div>
      </div>

      {/* Quantum Tabs / Filters */}
      <div className="quantum-tabs">
        <button
          onClick={() => setFilterAction('all')}
          className={`quantum-tab ${filterAction === 'all' ? 'quantum-tab--active' : ''}`}
        >
          <Activity className="w-4 h-4" />
          Tất cả
        </button>
        <button
          onClick={() => setFilterAction('document.uploaded')}
          className={`quantum-tab ${filterAction === 'document.uploaded' ? 'quantum-tab--active' : ''}`}
        >
          <Upload className="w-4 h-4" />
          Tải lên
        </button>
        <button
          onClick={() => setFilterAction('journal.proposed')}
          className={`quantum-tab ${filterAction === 'journal.proposed' ? 'quantum-tab--active' : ''}`}
        >
          <Edit3 className="w-4 h-4" />
          Đề xuất
        </button>
        <button
          onClick={() => setFilterAction('journal.approved')}
          className={`quantum-tab ${filterAction === 'journal.approved' ? 'quantum-tab--active' : ''}`}
        >
          <CheckCircle2 className="w-4 h-4" />
          Duyệt
        </button>
        <button
          onClick={() => setFilterAction('journal.rejected')}
          className={`quantum-tab ${filterAction === 'journal.rejected' ? 'quantum-tab--active' : ''}`}
        >
          <XCircle className="w-4 h-4" />
          Từ chối
        </button>
      </div>

      {/* Search */}
      <div className="flex gap-4 items-center">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Tìm kiếm theo hành động, người dùng, mã chứng từ..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-teal-500 bg-white"
          />
        </div>
      </div>

      {/* Quantum Stats Summary */}
      {!documentId && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="quantum-stat">
            <div className="quantum-stat__icon quantum-stat__icon--primary">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <div className="quantum-stat__value">{metrics.total_documents || 0}</div>
              <div className="quantum-stat__label">Tổng chứng từ</div>
            </div>
          </div>
          <div className="quantum-stat">
            <div className="quantum-stat__icon quantum-stat__icon--success">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <div>
              <div className="quantum-stat__value">{metrics.approved_documents || 0}</div>
              <div className="quantum-stat__label">Đã duyệt</div>
            </div>
          </div>
          <div className="quantum-stat">
            <div className="quantum-stat__icon quantum-stat__icon--warning">
              <Clock className="w-5 h-5" />
            </div>
            <div>
              <div className="quantum-stat__value">{metrics.pending_documents || 0}</div>
              <div className="quantum-stat__label">Đang xử lý</div>
            </div>
          </div>
          <div className="quantum-stat">
            <div className="quantum-stat__icon quantum-stat__icon--danger">
              <XCircle className="w-5 h-5" />
            </div>
            <div>
              <div className="quantum-stat__value">{metrics.rejected_documents || 0}</div>
              <div className="quantum-stat__label">Từ chối</div>
            </div>
          </div>
        </div>
      )}

      {/* Timeline */}
      <div className="space-y-3">
        {isLoading ? (
          <div className="quantum-card text-center py-12">
            <Clock className="w-12 h-12 mx-auto text-gray-300 mb-4 animate-pulse" />
            <p className="text-gray-500">Đang tải dữ liệu...</p>
          </div>
        ) : filteredEvents.length === 0 ? (
          <div className="quantum-card text-center py-12">
            <Shield className="w-12 h-12 mx-auto text-gray-300 mb-4" />
            <p className="text-gray-500 font-medium">Chưa có hoạt động nào</p>
            <p className="text-gray-400 text-sm mt-1">Các sự kiện sẽ hiển thị tại đây</p>
          </div>
        ) : (
          filteredEvents.map(event => (
            <EventCard key={event.id} event={event} />
          ))
        )}
      </div>

      {/* Load More */}
      {filteredEvents.length > 0 && (
        <div className="text-center">
          <button className="px-4 py-2 text-sm text-teal-600 hover:text-teal-800 font-medium">
            Xem thêm hoạt động cũ hơn
          </button>
        </div>
      )}

      {/* Module Chat Dock */}
      <ModuleChatDock module="evidence" />
    </div>
  );
}
