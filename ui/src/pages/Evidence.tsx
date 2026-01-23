import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  Clock,
  FileText,
  User,
  CheckCircle2,
  XCircle,
  ChevronRight,
  Filter,
  Search,
  ArrowLeft,
  FileCheck,
  Edit3,
  Upload,
  Brain,
  Bookmark,
  Printer,
  Download,
} from 'lucide-react';
import type { EvidenceEvent } from '../types';

// Mock evidence data
const MOCK_EVIDENCE: EvidenceEvent[] = [
  {
    id: 'evt-001',
    document_id: 'doc-001',
    timestamp: '2026-01-23T14:35:00Z',
    actor: 'user:nguyen.thi.mai@company.com',
    action: 'document.posted',
    payload: { ledger: 'GL', entry_id: 'JE-2026-0847' },
  },
  {
    id: 'evt-002',
    document_id: 'doc-001',
    timestamp: '2026-01-23T14:30:00Z',
    actor: 'user:nguyen.thi.mai@company.com',
    action: 'journal.approved',
    payload: { proposal_id: 'prop-001', note: 'Đã xác minh với NCC' },
  },
  {
    id: 'evt-003',
    document_id: 'doc-001',
    timestamp: '2026-01-23T11:20:00Z',
    actor: 'agent:accounting-agent',
    action: 'journal.proposed',
    payload: {
      proposal_id: 'prop-001',
      confidence: 0.92,
      entries_count: 2,
      total_debit: 11000000,
      total_credit: 11000000,
    },
  },
  {
    id: 'evt-004',
    document_id: 'doc-001',
    timestamp: '2026-01-23T11:15:00Z',
    actor: 'agent:ocr-extractor',
    action: 'extraction.completed',
    payload: {
      fields_extracted: 8,
      line_items: 3,
      confidence: 0.95,
    },
  },
  {
    id: 'evt-005',
    document_id: 'doc-001',
    timestamp: '2026-01-23T11:10:00Z',
    actor: 'agent:ocr-extractor',
    action: 'extraction.started',
    payload: { model: 'gpt-4o-vision', pages: 1 },
  },
  {
    id: 'evt-006',
    document_id: 'doc-001',
    timestamp: '2026-01-23T11:05:00Z',
    actor: 'user:le.van.tuan@company.com',
    action: 'document.uploaded',
    payload: { filename: 'hoadon_vpp_01.pdf', size_bytes: 245678, mime_type: 'application/pdf' },
  },
];

// More mock data for recent activity
const RECENT_ACTIVITY: EvidenceEvent[] = [
  {
    id: 'evt-r01',
    document_id: 'doc-015',
    timestamp: '2026-01-23T15:42:00Z',
    actor: 'user:nguyen.thi.mai@company.com',
    action: 'journal.approved',
    payload: { proposal_id: 'prop-015' },
  },
  {
    id: 'evt-r02',
    document_id: 'doc-014',
    timestamp: '2026-01-23T15:38:00Z',
    actor: 'agent:accounting-agent',
    action: 'journal.proposed',
    payload: { confidence: 0.88 },
  },
  {
    id: 'evt-r03',
    document_id: 'doc-013',
    timestamp: '2026-01-23T15:30:00Z',
    actor: 'user:le.van.tuan@company.com',
    action: 'document.uploaded',
    payload: { filename: 'invoice_abc.pdf' },
  },
  {
    id: 'evt-r04',
    document_id: 'doc-012',
    timestamp: '2026-01-23T15:25:00Z',
    actor: 'agent:ocr-extractor',
    action: 'extraction.completed',
    payload: { fields_extracted: 12 },
  },
  {
    id: 'evt-r05',
    document_id: 'doc-011',
    timestamp: '2026-01-23T15:20:00Z',
    actor: 'user:nguyen.thi.mai@company.com',
    action: 'journal.rejected',
    payload: { reason: 'Sai tài khoản đối ứng' },
  },
];

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
    <div className="flex gap-4 p-4 bg-white rounded-lg border hover:shadow-sm transition-shadow">
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

  // If documentId provided, show document-specific evidence
  const events = documentId ? MOCK_EVIDENCE : RECENT_ACTIVITY;

  const filteredEvents = events.filter(evt => {
    if (filterAction !== 'all' && evt.action !== filterAction) return false;
    if (searchQuery) {
      const searchLower = searchQuery.toLowerCase();
      return (
        evt.action.toLowerCase().includes(searchLower) ||
        evt.actor.toLowerCase().includes(searchLower) ||
        evt.document_id.toLowerCase().includes(searchLower)
      );
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {documentId && (
            <button
              onClick={() => navigate(-1)}
              className="p-2 rounded-lg hover:bg-gray-100"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
          )}
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              {documentId ? `Lịch sử chứng từ: ${documentId}` : 'Nhật ký hoạt động'}
            </h1>
            <p className="text-gray-500 text-sm mt-1">
              {documentId ? 'Timeline đầy đủ các sự kiện' : 'Hoạt động gần đây trong hệ thống'}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <button className="flex items-center gap-2 px-3 py-2 border rounded-lg hover:bg-gray-50">
            <Download className="w-4 h-4" />
            Xuất CSV
          </button>
          <button className="flex items-center gap-2 px-3 py-2 border rounded-lg hover:bg-gray-50">
            <Printer className="w-4 h-4" />
            In
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-4 items-center">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Tìm kiếm theo hành động, người dùng, mã chứng từ..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            value={filterAction}
            onChange={e => setFilterAction(e.target.value)}
            className="px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">Tất cả hành động</option>
            <option value="document.uploaded">Tải lên</option>
            <option value="extraction.completed">Trích xuất</option>
            <option value="journal.proposed">Đề xuất</option>
            <option value="journal.approved">Duyệt</option>
            <option value="journal.rejected">Từ chối</option>
            <option value="document.posted">Ghi sổ</option>
          </select>
        </div>
      </div>

      {/* Stats Summary */}
      {!documentId && (
        <div className="grid grid-cols-4 gap-4">
          <div className="bg-white p-4 rounded-xl border">
            <div className="text-2xl font-bold text-gray-900">47</div>
            <div className="text-sm text-gray-500">Chứng từ hôm nay</div>
          </div>
          <div className="bg-white p-4 rounded-xl border">
            <div className="text-2xl font-bold text-green-600">32</div>
            <div className="text-sm text-gray-500">Đã duyệt</div>
          </div>
          <div className="bg-white p-4 rounded-xl border">
            <div className="text-2xl font-bold text-amber-600">12</div>
            <div className="text-sm text-gray-500">Chờ duyệt</div>
          </div>
          <div className="bg-white p-4 rounded-xl border">
            <div className="text-2xl font-bold text-red-600">3</div>
            <div className="text-sm text-gray-500">Từ chối</div>
          </div>
        </div>
      )}

      {/* Timeline */}
      <div className="space-y-3">
        {filteredEvents.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-xl border">
            <Clock className="w-12 h-12 mx-auto text-gray-300 mb-4" />
            <p className="text-gray-500">Không tìm thấy sự kiện nào</p>
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
          <button className="px-4 py-2 text-sm text-blue-600 hover:text-blue-800">
            Xem thêm hoạt động cũ hơn
          </button>
        </div>
      )}
    </div>
  );
}
