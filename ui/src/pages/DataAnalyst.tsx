/**
 * Data Analyst Mode - P2 Feature
 * 
 * NL2SQL interface for accountants to query data using natural language
 * - Natural language to SQL translation
 * - Query history with favorites
 * - Results visualization (tables, charts)
 * - Export to CSV/Excel
 */

import { useState, useRef, useEffect } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  Database,
  Search,
  Play,
  History,
  Star,
  Download,
  Table2,
  BarChart3,
  RefreshCw,
  Sparkles,
  Copy,
  Check,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  FileSpreadsheet,
} from 'lucide-react';
import api from '../lib/api';

interface QueryResult {
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  execution_time_ms: number;
  sql: string;
}

interface QueryHistoryItem {
  id: string;
  question: string;
  sql: string;
  created_at: string;
  is_favorite: boolean;
  row_count?: number;
}

const SUGGESTED_QUERIES = [
  'Tổng doanh thu tháng này',
  'Top 10 nhà cung cấp theo số tiền mua hàng',
  'Số hóa đơn chưa thanh toán theo nhà cung cấp',
  'Chi tiết các bút toán tuần này',
  'So sánh doanh thu 3 tháng gần nhất',
];

export default function DataAnalyst() {
  const [question, setQuestion] = useState('');
  const [showHistory, setShowHistory] = useState(false);
  const [showSql, setShowSql] = useState(false);
  const [viewMode, setViewMode] = useState<'table' | 'chart'>('table');
  const [copied, setCopied] = useState(false);
  const [queryResult, setQueryResult] = useState<QueryResult | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Query history
  const { data: history = [], refetch: refetchHistory } = useQuery({
    queryKey: ['query-history'],
    queryFn: async () => {
      try {
        const res = await api.get('/v1/analyst/history');
        return res.data as QueryHistoryItem[];
      } catch {
        return [];
      }
    },
    staleTime: 30000,
  });

  // NL2SQL mutation
  const queryMutation = useMutation({
    mutationFn: async (nlQuestion: string) => {
      const response = await api.post('/v1/analyst/query', { question: nlQuestion });
      return response.data as QueryResult;
    },
    onSuccess: (data) => {
      setQueryResult(data);
      refetchHistory();
    },
  });

  const handleQuery = () => {
    if (!question.trim() || queryMutation.isPending) return;
    queryMutation.mutate(question.trim());
  };

  const handleSuggestedQuery = (q: string) => {
    setQuestion(q);
    inputRef.current?.focus();
  };

  const handleHistoryClick = (item: QueryHistoryItem) => {
    setQuestion(item.question);
    setShowHistory(false);
    inputRef.current?.focus();
  };

  const handleCopySql = () => {
    if (queryResult?.sql) {
      navigator.clipboard.writeText(queryResult.sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleExport = (format: 'csv' | 'excel') => {
    if (!queryResult?.rows.length) return;
    
    if (format === 'csv') {
      const headers = queryResult.columns.join(',');
      const rows = queryResult.rows.map(row => 
        queryResult.columns.map(col => JSON.stringify(row[col] ?? '')).join(',')
      );
      const csv = [headers, ...rows].join('\n');
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `query_result_${Date.now()}.csv`;
      link.click();
    }
    // Excel export would need a library like xlsx
  };

  const formatCellValue = (value: unknown): string => {
    if (value === null || value === undefined) return '-';
    if (typeof value === 'number') {
      return value.toLocaleString('vi-VN');
    }
    return String(value);
  };

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = `${Math.min(inputRef.current.scrollHeight, 120)}px`;
    }
  }, [question]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center">
              <Database className="w-5 h-5 text-white" />
            </div>
            Data Analyst
          </h1>
          <p className="text-gray-500 text-sm mt-1">Truy vấn dữ liệu bằng ngôn ngữ tự nhiên</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowHistory(!showHistory)}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors ${
              showHistory ? 'bg-purple-50 border-purple-200 text-purple-700' : 'hover:bg-gray-50'
            }`}
          >
            <History className="w-4 h-4" />
            Lịch sử
          </button>
        </div>
      </div>

      {/* Query Input */}
      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        <div className="p-4 border-b bg-gradient-to-r from-purple-50 to-indigo-50">
          <div className="flex items-start gap-3">
            <Sparkles className="w-5 h-5 text-purple-600 mt-1" />
            <div className="flex-1">
              <textarea
                ref={inputRef}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleQuery();
                  }
                }}
                placeholder="Nhập câu hỏi về dữ liệu, ví dụ: 'Tổng doanh thu tháng này'..."
                className="w-full bg-white border rounded-lg px-4 py-3 resize-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                rows={1}
              />
              <div className="flex items-center justify-between mt-3">
                <div className="flex flex-wrap gap-2">
                  {SUGGESTED_QUERIES.slice(0, 3).map((q, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSuggestedQuery(q)}
                      className="text-xs px-2 py-1 bg-white border rounded-full hover:bg-purple-50 hover:border-purple-200 transition-colors"
                    >
                      {q}
                    </button>
                  ))}
                </div>
                <button
                  onClick={handleQuery}
                  disabled={!question.trim() || queryMutation.isPending}
                  className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {queryMutation.isPending ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <Play className="w-4 h-4" />
                  )}
                  Truy vấn
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Error */}
        {queryMutation.isError && (
          <div className="p-4 bg-red-50 border-b border-red-100">
            <div className="flex items-start gap-3 text-red-700">
              <AlertCircle className="w-5 h-5 mt-0.5" />
              <div>
                <p className="font-medium">Không thể thực hiện truy vấn</p>
                <p className="text-sm mt-1">
                  {queryMutation.error instanceof Error 
                    ? queryMutation.error.message 
                    : 'Vui lòng thử lại với câu hỏi khác'}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Results */}
        {queryResult && (
          <div className="divide-y">
            {/* SQL Preview */}
            <div className="p-4">
              <button
                onClick={() => setShowSql(!showSql)}
                className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700"
              >
                {showSql ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                SQL Query
              </button>
              {showSql && (
                <div className="mt-2 relative">
                  <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg text-sm overflow-x-auto">
                    {queryResult.sql}
                  </pre>
                  <button
                    onClick={handleCopySql}
                    className="absolute top-2 right-2 p-2 bg-gray-700 hover:bg-gray-600 rounded text-white"
                  >
                    {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>
              )}
            </div>

            {/* Result Stats */}
            <div className="p-4 bg-gray-50 flex items-center justify-between">
              <div className="flex items-center gap-4 text-sm text-gray-600">
                <span>{queryResult.row_count.toLocaleString()} kết quả</span>
                <span>•</span>
                <span>{queryResult.execution_time_ms}ms</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex border rounded-lg overflow-hidden">
                  <button
                    onClick={() => setViewMode('table')}
                    className={`p-2 ${viewMode === 'table' ? 'bg-purple-100 text-purple-700' : 'hover:bg-gray-100'}`}
                  >
                    <Table2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setViewMode('chart')}
                    className={`p-2 ${viewMode === 'chart' ? 'bg-purple-100 text-purple-700' : 'hover:bg-gray-100'}`}
                  >
                    <BarChart3 className="w-4 h-4" />
                  </button>
                </div>
                <button
                  onClick={() => handleExport('csv')}
                  className="flex items-center gap-1 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50"
                >
                  <Download className="w-4 h-4" />
                  CSV
                </button>
              </div>
            </div>

            {/* Data Table */}
            {viewMode === 'table' && queryResult.rows.length > 0 && (
              <div className="overflow-x-auto max-h-96">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50 sticky top-0">
                    <tr>
                      {queryResult.columns.map((col, idx) => (
                        <th
                          key={idx}
                          className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider"
                        >
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {queryResult.rows.slice(0, 100).map((row, rowIdx) => (
                      <tr key={rowIdx} className="hover:bg-gray-50">
                        {queryResult.columns.map((col, colIdx) => (
                          <td key={colIdx} className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap">
                            {formatCellValue(row[col])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                {queryResult.row_count > 100 && (
                  <div className="p-3 text-center text-sm text-gray-500 bg-gray-50 border-t">
                    Hiển thị 100/{queryResult.row_count} kết quả. Export để xem tất cả.
                  </div>
                )}
              </div>
            )}

            {/* Chart View Placeholder */}
            {viewMode === 'chart' && (
              <div className="p-12 text-center text-gray-500">
                <BarChart3 className="w-12 h-12 mx-auto text-gray-300 mb-3" />
                <p>Chart visualization coming soon</p>
                <p className="text-sm text-gray-400 mt-1">Sử dụng view Table để xem dữ liệu</p>
              </div>
            )}

            {/* No Results */}
            {queryResult.rows.length === 0 && (
              <div className="p-12 text-center text-gray-500">
                <Search className="w-12 h-12 mx-auto text-gray-300 mb-3" />
                <p>Không tìm thấy kết quả</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* History Panel */}
      {showHistory && (
        <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b bg-gray-50 flex items-center justify-between">
            <h2 className="font-semibold text-gray-900">Lịch sử truy vấn</h2>
          </div>
          <div className="divide-y max-h-80 overflow-auto">
            {history.length === 0 ? (
              <div className="p-8 text-center text-gray-500">
                <History className="w-10 h-10 mx-auto text-gray-300 mb-3" />
                <p>Chưa có lịch sử truy vấn</p>
              </div>
            ) : (
              history.map((item) => (
                <div
                  key={item.id}
                  className="p-4 hover:bg-gray-50 cursor-pointer transition-colors"
                  onClick={() => handleHistoryClick(item)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-900">{item.question}</p>
                      <p className="text-xs text-gray-500 mt-1 font-mono truncate">{item.sql}</p>
                    </div>
                    <div className="flex items-center gap-2 ml-4">
                      {item.is_favorite && <Star className="w-4 h-4 text-yellow-500 fill-yellow-500" />}
                      {item.row_count !== undefined && (
                        <span className="text-xs text-gray-400">{item.row_count} rows</span>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Coming Soon Features */}
      <div className="bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-200 rounded-xl p-6">
        <h3 className="font-semibold text-purple-900">Tính năng NL2SQL (Beta)</h3>
        <ul className="mt-3 text-sm text-purple-700 space-y-2">
          <li className="flex items-start gap-2">
            <Sparkles className="w-4 h-4 mt-0.5 flex-shrink-0" />
            Tự động chuyển đổi câu hỏi tiếng Việt thành SQL
          </li>
          <li className="flex items-start gap-2">
            <FileSpreadsheet className="w-4 h-4 mt-0.5 flex-shrink-0" />
            Export kết quả sang CSV, Excel
          </li>
          <li className="flex items-start gap-2">
            <BarChart3 className="w-4 h-4 mt-0.5 flex-shrink-0" />
            Visualization với charts (coming soon)
          </li>
        </ul>
      </div>
    </div>
  );
}
