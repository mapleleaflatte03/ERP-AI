/**
 * Analytics Module v2
 * AI-powered financial analysis assistant with:
 * - Chat interface (AI Assistant)
 * - Schema Explorer & SQL Editor
 * - KPI Dashboard
 * - Forecasting
 * - Dataset Management
 */

import { useState, useRef, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  MessageSquare,
  Database,
  BarChart3,
  TrendingUp,
  FileSpreadsheet,
  Send,
  RefreshCw,
  Play,
  Sparkles,
  ArrowUp,
  ArrowDown,
  Minus,
  Table,
  Upload,
  X,
  Users,
  DollarSign,
  FileText,
  Clock,
  Bot,
  User,
} from 'lucide-react';

// Types
interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
  toolCalls?: any[];
  toolResults?: any[];
  visualizations?: any[];
}

interface KPIMetric {
  name: string;
  value: number | null;
  change?: number;
  change_direction?: 'up' | 'down' | 'stable';
  formatted?: string;
}

interface Dataset {
  name: string;
  row_count: number;
  column_count: number;
  description?: string;
}

// Tab type
type TabType = 'chat' | 'explorer' | 'kpis' | 'forecast' | 'datasets';

export default function Analytics() {
  const [activeTab, setActiveTab] = useState<TabType>('chat');
  
  return (
    <div className="h-[calc(100vh-120px)] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            Analytics
          </h1>
          <p className="text-gray-500 text-sm mt-1">Trợ lý phân tích tài chính AI</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-4">
        <nav className="flex gap-1">
          {[
            { id: 'chat', label: 'Chat', icon: MessageSquare },
            { id: 'explorer', label: 'Explorer', icon: Database },
            { id: 'kpis', label: 'KPIs', icon: BarChart3 },
            { id: 'forecast', label: 'Dự báo', icon: TrendingUp },
            { id: 'datasets', label: 'Datasets', icon: FileSpreadsheet },
          ].map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id as TabType)}
              className={`px-4 py-2.5 rounded-t-lg font-medium text-sm transition-colors flex items-center gap-2 ${
                activeTab === id
                  ? 'bg-white border border-b-0 border-gray-200 text-violet-600 -mb-px'
                  : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-hidden bg-white rounded-xl border shadow-sm">
        {activeTab === 'chat' && <ChatTab />}
        {activeTab === 'explorer' && <ExplorerTab />}
        {activeTab === 'kpis' && <KPIsTab />}
        {activeTab === 'forecast' && <ForecastTab />}
        {activeTab === 'datasets' && <DatasetsTab />}
      </div>
    </div>
  );
}

// =============================================================================
// Chat Tab - AI Assistant
// =============================================================================

function ChatTab() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const chatMutation = useMutation({
    mutationFn: async (message: string) => {
      const res = await fetch('/v1/analytics/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, session_id: sessionId }),
      });
      return res.json();
    },
    onSuccess: (data) => {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.message,
          toolCalls: data.tool_calls,
          toolResults: data.tool_results,
          visualizations: data.visualizations,
        },
      ]);
      setSessionId(data.session_id);
    },
  });

  const handleSend = () => {
    if (!input.trim() || chatMutation.isPending) return;
    
    setMessages((prev) => [...prev, { role: 'user', content: input }]);
    chatMutation.mutate(input);
    setInput('');
  };

  const suggestions = [
    'Tổng doanh thu tháng này là bao nhiêu?',
    'Top 5 nhà cung cấp theo số tiền',
    'So sánh doanh thu 3 tháng gần nhất',
    'Dự báo doanh thu 30 ngày tới',
  ];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="h-full flex flex-col">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-gray-500">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-100 to-purple-100 flex items-center justify-center mb-4">
              <Bot className="w-8 h-8 text-violet-600" />
            </div>
            <h3 className="font-semibold text-gray-900 mb-2">Trợ lý phân tích AI</h3>
            <p className="text-sm text-center max-w-md mb-6">
              Hỏi bất kỳ câu hỏi nào về dữ liệu tài chính của bạn. Tôi có thể truy vấn, 
              phân tích và tạo biểu đồ.
            </p>
            <div className="flex flex-wrap gap-2 justify-center max-w-lg">
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  onClick={() => setInput(s)}
                  className="px-3 py-1.5 bg-gray-100 hover:bg-violet-100 text-gray-700 hover:text-violet-700 rounded-full text-sm transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}
            >
              {msg.role === 'assistant' && (
                <div className="w-8 h-8 rounded-lg bg-violet-100 flex items-center justify-center flex-shrink-0">
                  <Bot className="w-4 h-4 text-violet-600" />
                </div>
              )}
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                  msg.role === 'user'
                    ? 'bg-violet-600 text-white'
                    : 'bg-gray-100 text-gray-900'
                }`}
              >
                <div className="whitespace-pre-wrap">{msg.content}</div>
                
                {/* Tool Results */}
                {msg.toolResults && msg.toolResults.length > 0 && (
                  <div className="mt-3 space-y-2">
                    {msg.toolResults.map((tr: any, i: number) => (
                      <div key={i} className="bg-white rounded-lg p-3 text-sm">
                        <div className="font-medium text-violet-600 mb-1">
                          📊 {tr.tool}
                        </div>
                        {/* List Datasets Result */}
                        {tr.result?.datasets && (
                          <div className="space-y-1 text-sm">
                            {tr.result.datasets.map((ds: any, di: number) => (
                              <div key={di} className="flex justify-between py-1 border-b border-gray-100 last:border-0">
                                <span className="text-gray-800">{ds.name}</span>
                                <span className="text-violet-600 font-medium">{ds.rows?.toLocaleString() || 0} rows</span>
                              </div>
                            ))}
                          </div>
                        )}
                        {/* Table Data Result */}
                        {tr.result?.rows && !tr.result?.datasets && (
                          <div className="overflow-x-auto">
                            <table className="min-w-full text-xs">
                              <thead>
                                <tr>
                                  {tr.result.columns?.slice(0, 5).map((col: string) => (
                                    <th key={col} className="px-2 py-1 text-left font-medium text-gray-600">
                                      {col}
                                    </th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {tr.result.rows.slice(0, 5).map((row: any, ri: number) => (
                                  <tr key={ri}>
                                    {tr.result.columns?.slice(0, 5).map((col: string) => (
                                      <td key={col} className="px-2 py-1 text-gray-700">
                                        {formatValue(row[col])}
                                      </td>
                                    ))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                            {tr.result.row_count > 5 && (
                              <div className="text-gray-500 text-xs mt-1">
                                + {tr.result.row_count - 5} dòng khác
                              </div>
                            )}
                          </div>
                        )}
                        {/* Stats/Describe Result */}
                        {tr.result?.stats && (
                          <div className="text-sm space-y-1">
                            {Object.entries(tr.result.stats).slice(0, 5).map(([k, v]: [string, any]) => (
                              <div key={k} className="flex justify-between">
                                <span className="text-gray-600">{k}</span>
                                <span className="font-medium">{typeof v === 'number' ? v.toLocaleString() : String(v)}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
              {msg.role === 'user' && (
                <div className="w-8 h-8 rounded-lg bg-gray-200 flex items-center justify-center flex-shrink-0">
                  <User className="w-4 h-4 text-gray-600" />
                </div>
              )}
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Hỏi về dữ liệu của bạn..."
            className="flex-1 px-4 py-3 border rounded-xl focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || chatMutation.isPending}
            className="px-4 py-3 bg-violet-600 text-white rounded-xl hover:bg-violet-700 disabled:opacity-50 flex items-center gap-2"
          >
            {chatMutation.isPending ? (
              <RefreshCw className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Explorer Tab - Schema & SQL
// =============================================================================

function ExplorerTab() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any>(null);

  const { data: schema, isLoading: schemaLoading } = useQuery({
    queryKey: ['analytics-schema'],
    queryFn: async () => {
      const res = await fetch('/v1/analytics/schema');
      return res.json();
    },
  });

  const queryMutation = useMutation({
    mutationFn: async (question: string) => {
      const res = await fetch('/v1/analytics/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, execute: true }),
      });
      return res.json();
    },
    onSuccess: (data) => setResults(data),
  });

  return (
    <div className="h-full flex">
      {/* Schema sidebar */}
      <div className="w-64 border-r overflow-y-auto p-4">
        <h3 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <Database className="w-4 h-4" />
          Tables
        </h3>
        {schemaLoading ? (
          <div className="text-gray-500 text-sm">Loading...</div>
        ) : (
          <div className="space-y-2">
            {schema?.tables?.map((table: any) => (
              <div key={table.name} className="group">
                <button className="w-full text-left px-2 py-1.5 rounded hover:bg-gray-100 flex items-center justify-between">
                  <span className="font-medium text-sm">{table.name}</span>
                  <span className="text-xs text-gray-400">{table.row_count}</span>
                </button>
                <div className="ml-4 mt-1 space-y-0.5 hidden group-hover:block">
                  {table.columns?.slice(0, 5).map((col: any) => (
                    <div key={col.name} className="text-xs text-gray-500 flex justify-between">
                      <span>{col.name}</span>
                      <span className="text-gray-400">{col.type}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Query area */}
      <div className="flex-1 flex flex-col">
        <div className="p-4 border-b">
          <div className="flex gap-2">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && queryMutation.mutate(query)}
              placeholder="Nhập câu hỏi hoặc SQL..."
              className="flex-1 px-4 py-2 border rounded-lg focus:ring-2 focus:ring-violet-500"
            />
            <button
              onClick={() => queryMutation.mutate(query)}
              disabled={!query.trim() || queryMutation.isPending}
              className="px-4 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-50 flex items-center gap-2"
            >
              {queryMutation.isPending ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              Run
            </button>
          </div>
        </div>

        {/* Results */}
        <div className="flex-1 overflow-auto p-4">
          {results ? (
            results.error ? (
              <div className="text-red-500 p-4 bg-red-50 rounded-lg">
                {results.error}
              </div>
            ) : (
              <div>
                {results.sql && (
                  <div className="mb-4 p-3 bg-gray-50 rounded-lg">
                    <div className="text-xs text-gray-500 mb-1">SQL:</div>
                    <code className="text-sm text-gray-700">{results.sql}</code>
                  </div>
                )}
                <div className="text-sm text-gray-500 mb-2">
                  {results.results?.row_count || results.row_count || 0} kết quả 
                  • {results.results?.execution_time_ms || results.execution_time_ms}ms
                </div>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        {(results.results?.columns || results.columns)?.map((col: string) => (
                          <th key={col} className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase">
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {(results.results?.rows || results.rows)?.slice(0, 100).map((row: any, idx: number) => (
                        <tr key={idx} className="hover:bg-gray-50">
                          {(results.results?.columns || results.columns)?.map((col: string) => (
                            <td key={col} className="px-4 py-2 text-sm text-gray-700">
                              {formatValue(row[col])}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )
          ) : (
            <div className="h-full flex items-center justify-center text-gray-500">
              <div className="text-center">
                <Table className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                <p>Chạy một truy vấn để xem kết quả</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// KPIs Tab
// =============================================================================

function KPIsTab() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['analytics-kpis'],
    queryFn: async () => {
      const res = await fetch('/v1/analytics/kpis');
      return res.json();
    },
  });

  const KPI_ICONS: Record<string, typeof DollarSign> = {
    'Tổng doanh thu': DollarSign,
    'Số hóa đơn': FileText,
    'TB giá trị HĐ': BarChart3,
    'Số NCC': Users,
    'Chờ duyệt': Clock,
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold text-gray-900">KPI Dashboard</h2>
        <button
          onClick={() => refetch()}
          className="p-2 hover:bg-gray-100 rounded-lg"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {data?.metrics?.map((metric: KPIMetric) => {
          const Icon = KPI_ICONS[metric.name] || BarChart3;
          return (
            <div
              key={metric.name}
              className="bg-gray-50 rounded-xl p-4 hover:bg-gray-100 transition-colors"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="w-10 h-10 rounded-lg bg-violet-100 flex items-center justify-center">
                  <Icon className="w-5 h-5 text-violet-600" />
                </div>
                {metric.change !== undefined && metric.change !== null && (
                  <div
                    className={`flex items-center text-sm ${
                      metric.change_direction === 'up'
                        ? 'text-green-600'
                        : metric.change_direction === 'down'
                        ? 'text-red-600'
                        : 'text-gray-500'
                    }`}
                  >
                    {metric.change_direction === 'up' ? (
                      <ArrowUp className="w-4 h-4" />
                    ) : metric.change_direction === 'down' ? (
                      <ArrowDown className="w-4 h-4" />
                    ) : (
                      <Minus className="w-4 h-4" />
                    )}
                    {Math.abs(metric.change)}%
                  </div>
                )}
              </div>
              <div className="text-2xl font-bold text-gray-900">
                {metric.formatted || formatValue(metric.value)}
              </div>
              <div className="text-sm text-gray-500">{metric.name}</div>
            </div>
          );
        })}
      </div>

      {/* Monthly Summary Chart Placeholder */}
      <div className="mt-8">
        <h3 className="font-semibold text-gray-900 mb-4">Tổng hợp theo tháng</h3>
        <MonthlySummaryChart />
      </div>
    </div>
  );
}

function MonthlySummaryChart() {
  const { data, isLoading } = useQuery({
    queryKey: ['monthly-summary'],
    queryFn: async () => {
      const res = await fetch('/v1/analytics/monthly-summary?months=6');
      return res.json();
    },
  });

  if (isLoading) {
    return <div className="h-64 flex items-center justify-center text-gray-500">Loading...</div>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Tháng</th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-gray-600 uppercase">Số HĐ</th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-gray-600 uppercase">Tổng tiền</th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-gray-600 uppercase">TB/HĐ</th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-gray-600 uppercase">Số NCC</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {data?.rows?.map((row: any, idx: number) => (
            <tr key={idx} className="hover:bg-gray-50">
              <td className="px-4 py-3 text-sm font-medium text-gray-900">
                {row.month ? new Date(row.month).toLocaleDateString('vi-VN', { month: 'short', year: 'numeric' }) : '-'}
              </td>
              <td className="px-4 py-3 text-sm text-right text-gray-700">{row.invoice_count}</td>
              <td className="px-4 py-3 text-sm text-right text-gray-700">{formatCurrency(row.total_revenue)}</td>
              <td className="px-4 py-3 text-sm text-right text-gray-700">{formatCurrency(row.avg_invoice_value)}</td>
              <td className="px-4 py-3 text-sm text-right text-gray-700">{row.vendor_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// =============================================================================
// Forecast Tab
// =============================================================================

function ForecastTab() {
  const [metric, setMetric] = useState('revenue');
  const [horizon, setHorizon] = useState(30);
  const [model, setModel] = useState('linear');

  const forecastMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch('/v1/analytics/forecast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ metric, horizon, model }),
      });
      return res.json();
    },
  });

  return (
    <div className="p-6">
      <div className="flex items-center gap-4 mb-6">
        <select
          value={metric}
          onChange={(e) => setMetric(e.target.value)}
          className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-violet-500"
        >
          <option value="revenue">Doanh thu</option>
          <option value="invoice_count">Số hóa đơn</option>
          <option value="avg_invoice_value">TB giá trị HĐ</option>
        </select>

        <select
          value={horizon}
          onChange={(e) => setHorizon(Number(e.target.value))}
          className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-violet-500"
        >
          <option value={7}>7 ngày</option>
          <option value={30}>30 ngày</option>
          <option value={60}>60 ngày</option>
          <option value={90}>90 ngày</option>
        </select>

        <select
          value={model}
          onChange={(e) => setModel(e.target.value)}
          className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-violet-500"
        >
          <option value="linear">Linear (nhanh)</option>
          <option value="prophet">Prophet (chính xác)</option>
        </select>

        <button
          onClick={() => forecastMutation.mutate()}
          disabled={forecastMutation.isPending}
          className="px-4 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-50 flex items-center gap-2"
        >
          {forecastMutation.isPending ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : (
            <TrendingUp className="w-4 h-4" />
          )}
          Dự báo
        </button>
      </div>

      {/* Results */}
      {forecastMutation.data && (
        <div>
          <h3 className="font-semibold text-gray-900 mb-4">
            Dự báo {forecastMutation.data.metric} - {forecastMutation.data.horizon} ngày
          </h3>
          
          {/* Simple table view of forecast */}
          <div className="grid grid-cols-2 gap-6">
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2">Dữ liệu lịch sử</h4>
              <div className="max-h-64 overflow-y-auto">
                <table className="min-w-full text-sm">
                  <thead className="bg-gray-50 sticky top-0">
                    <tr>
                      <th className="px-3 py-2 text-left">Ngày</th>
                      <th className="px-3 py-2 text-right">Giá trị</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {forecastMutation.data.historical?.slice(-10).map((p: any, i: number) => (
                      <tr key={i}>
                        <td className="px-3 py-2">{p.date}</td>
                        <td className="px-3 py-2 text-right">{formatValue(p.value)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2">Dự báo</h4>
              <div className="max-h-64 overflow-y-auto">
                <table className="min-w-full text-sm">
                  <thead className="bg-violet-50 sticky top-0">
                    <tr>
                      <th className="px-3 py-2 text-left">Ngày</th>
                      <th className="px-3 py-2 text-right">Dự báo</th>
                      <th className="px-3 py-2 text-right">Khoảng</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {forecastMutation.data.forecast?.map((p: any, i: number) => (
                      <tr key={i}>
                        <td className="px-3 py-2">{p.date}</td>
                        <td className="px-3 py-2 text-right font-medium text-violet-600">
                          {formatValue(p.value)}
                        </td>
                        <td className="px-3 py-2 text-right text-gray-500 text-xs">
                          {formatValue(p.lower_bound)} - {formatValue(p.upper_bound)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}

      {!forecastMutation.data && !forecastMutation.isPending && (
        <div className="h-64 flex items-center justify-center text-gray-500">
          <div className="text-center">
            <TrendingUp className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <p>Chọn metric và nhấn "Dự báo" để xem kết quả</p>
          </div>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Datasets Tab
// =============================================================================

function DatasetsTab() {
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['analytics-datasets'],
    queryFn: async () => {
      const res = await fetch('/v1/analytics/datasets');
      return res.json();
    },
  });

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('name', file.name.replace(/\.[^/.]+$/, ''));
      
      const res = await fetch('/v1/analytics/datasets', {
        method: 'POST',
        body: formData,
      });
      return res.json();
    },
    onSuccess: () => {
      setUploadFiles([]);
      refetch();
    },
  });

  const handleUpload = () => {
    uploadFiles.forEach((file) => uploadMutation.mutate(file));
  };

  return (
    <div className="p-6">
      {/* Upload section */}
      <div className="border-2 border-dashed border-gray-300 rounded-xl p-6 mb-6 hover:border-violet-400 transition-colors">
        <input
          type="file"
          ref={fileInputRef}
          onChange={(e) => setUploadFiles(Array.from(e.target.files || []))}
          accept=".csv,.xlsx,.xls"
          multiple
          className="hidden"
        />
        
        <div className="flex items-center justify-center gap-4">
          <button
            onClick={() => fileInputRef.current?.click()}
            className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-gray-700"
          >
            <FileSpreadsheet className="w-5 h-5" />
            Chọn file CSV/Excel
          </button>

          {uploadFiles.length > 0 && (
            <>
              <div className="flex gap-2">
                {uploadFiles.map((f, i) => (
                  <span
                    key={i}
                    className="px-3 py-1 bg-violet-100 text-violet-700 rounded-full text-sm flex items-center gap-2"
                  >
                    {f.name}
                    <button onClick={() => setUploadFiles((prev) => prev.filter((_, idx) => idx !== i))}>
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
              <button
                onClick={handleUpload}
                disabled={uploadMutation.isPending}
                className="px-4 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-50 flex items-center gap-2"
              >
                {uploadMutation.isPending ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Upload className="w-4 h-4" />
                )}
                Upload
              </button>
            </>
          )}
        </div>
      </div>

      {/* Datasets list */}
      <h3 className="font-semibold text-gray-900 mb-4">Datasets</h3>
      
      {isLoading ? (
        <div className="text-center text-gray-500 py-8">Loading...</div>
      ) : data?.datasets?.length === 0 ? (
        <div className="text-center text-gray-500 py-8">
          <Database className="w-12 h-12 mx-auto mb-3 text-gray-300" />
          <p>Chưa có dataset nào</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data?.datasets?.map((ds: Dataset) => (
            <div
              key={ds.name}
              className="border rounded-xl p-4 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between">
                <div className="w-10 h-10 rounded-lg bg-violet-100 flex items-center justify-center">
                  <FileSpreadsheet className="w-5 h-5 text-violet-600" />
                </div>
              </div>
              <h4 className="font-medium text-gray-900 mt-3">{ds.name}</h4>
              <p className="text-sm text-gray-500 mt-1">{ds.description}</p>
              <div className="flex gap-4 mt-3 text-sm text-gray-600">
                <span>{ds.row_count?.toLocaleString()} dòng</span>
                <span>{ds.column_count} cột</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Utility Functions
// =============================================================================

function formatValue(val: any): string {
  if (val === null || val === undefined) return '-';
  if (typeof val === 'number') {
    if (val >= 1000000) {
      return (val / 1000000).toFixed(1) + 'M';
    }
    return val.toLocaleString('vi-VN');
  }
  return String(val);
}

function formatCurrency(val: any): string {
  if (val === null || val === undefined) return '-';
  const num = typeof val === 'number' ? val : parseFloat(val);
  if (isNaN(num)) return '-';
  if (num >= 1000000000) {
    return (num / 1000000000).toFixed(1) + 'B';
  }
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M';
  }
  return num.toLocaleString('vi-VN');
}
