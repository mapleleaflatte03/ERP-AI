/**
 * Analyze Module - Unified Reports + Data Analyst
 * 
 * Combines:
 * - Tab 1: "Báo cáo" - Pre-built reports from /v1/analyze/reports
 * - Tab 2: "Data Analyze" - Dataset upload + NL2SQL query
 */

import { useState, useRef } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  BarChart3,
  Database,
  FileSpreadsheet,
  Upload,
  Play,
  RefreshCw,
  Calendar,
  TrendingUp,
  Users,
  FileText,
  AlertCircle,
  X,
  Sparkles,
  Clock,
} from 'lucide-react';
import api from '../lib/api';

interface Report {
  id: string;
  name: string;
  description: string;
}

interface Dataset {
  id: string;
  name: string;
  filename: string;
  row_count: number;
  columns: string[];
  status: string;
  created_at: string;
}

const REPORT_ICONS: Record<string, typeof BarChart3> = {
  monthly_summary: Calendar,
  vendor_summary: Users,
  high_value_invoices: TrendingUp,
  recent_invoices: Clock,
  approval_status: FileText,
};

export default function Analyze() {
  const [activeTab, setActiveTab] = useState<'reports' | 'data'>('reports');
  const [selectedReport, setSelectedReport] = useState<string | null>(null);
  const [reportResult, setReportResult] = useState<any>(null);
  const [reportLoading, setReportLoading] = useState(false);
  
  // Dataset upload state
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Query state for NL2SQL
  const [queryText, setQueryText] = useState('');
  const [queryResult, setQueryResult] = useState<any>(null);

  // Fetch reports list
  const { data: reportsData, isLoading: reportsLoading } = useQuery({
    queryKey: ['analyze-reports'],
    queryFn: () => api.getAnalyzeReports(),
    staleTime: 60000,
  });

  // Fetch datasets list
  const { data: datasetsData, isLoading: datasetsLoading, refetch: refetchDatasets } = useQuery({
    queryKey: ['analyze-datasets'],
    queryFn: () => api.getDatasets(),
    staleTime: 30000,
  });

  const reports: Report[] = reportsData?.reports || [];
  const datasets: Dataset[] = datasetsData?.datasets || [];

  // Run report mutation
  const runReport = async (reportId: string) => {
    setReportLoading(true);
    setSelectedReport(reportId);
    try {
      const result = await api.runAnalyzeReport(reportId);
      setReportResult(result);
    } catch (err) {
      console.error('Error running report:', err);
      setReportResult({ error: 'Không thể chạy báo cáo' });
    } finally {
      setReportLoading(false);
    }
  };

  // Upload dataset
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    const validFiles = files.filter(f => 
      f.name.endsWith('.csv') || f.name.endsWith('.xlsx') || f.name.endsWith('.xls')
    );
    if (validFiles.length > 0) {
      setUploadFiles(validFiles);
    }
  };

  const handleUpload = async () => {
    if (uploadFiles.length === 0) return;
    setUploading(true);
    try {
      for (const file of uploadFiles) {
        await api.uploadDataset(file, file.name);
      }
      setUploadFiles([]);
      refetchDatasets();
    } catch (err) {
      console.error('Upload error:', err);
    } finally {
      setUploading(false);
    }
  };

  // NL2SQL query
  const queryMutation = useMutation({
    mutationFn: (question: string) => api.runAnalyzeQuery(question),
    onSuccess: (data) => setQueryResult(data),
  });

  const handleQuery = () => {
    if (!queryText.trim()) return;
    queryMutation.mutate(queryText);
  };

  const formatValue = (val: any): string => {
    if (val === null || val === undefined) return '-';
    if (typeof val === 'number') {
      return val.toLocaleString('vi-VN');
    }
    return String(val);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
              <BarChart3 className="w-5 h-5 text-white" />
            </div>
            Analyze
          </h1>
          <p className="text-gray-500 text-sm mt-1">Báo cáo và phân tích dữ liệu</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-6">
          <button
            onClick={() => setActiveTab('reports')}
            className={`pb-3 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'reports'
                ? 'border-emerald-500 text-emerald-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <div className="flex items-center gap-2">
              <BarChart3 className="w-4 h-4" />
              Báo cáo
            </div>
          </button>
          <button
            onClick={() => setActiveTab('data')}
            className={`pb-3 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'data'
                ? 'border-emerald-500 text-emerald-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4" />
              Data Analyze
              <span className="px-1.5 py-0.5 text-[10px] bg-emerald-100 text-emerald-700 rounded">BETA</span>
            </div>
          </button>
        </nav>
      </div>

      {/* Tab: Reports */}
      {activeTab === 'reports' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Reports List */}
          <div className="lg:col-span-1 space-y-3">
            <h2 className="font-semibold text-gray-900 mb-3">Báo cáo có sẵn</h2>
            {reportsLoading ? (
              <div className="p-4 text-center text-gray-500">
                <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2" />
                Đang tải...
              </div>
            ) : reports.length === 0 ? (
              <div className="p-4 text-center text-gray-500">
                <FileText className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                Chưa có báo cáo
              </div>
            ) : (
              reports.map((report) => {
                const Icon = REPORT_ICONS[report.id] || BarChart3;
                const isSelected = selectedReport === report.id;
                return (
                  <button
                    key={report.id}
                    onClick={() => runReport(report.id)}
                    disabled={reportLoading}
                    className={`w-full text-left p-4 rounded-xl border transition-all ${
                      isSelected
                        ? 'bg-emerald-50 border-emerald-300 ring-2 ring-emerald-500'
                        : 'bg-white hover:bg-gray-50 border-gray-200'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                        isSelected ? 'bg-emerald-100' : 'bg-gray-100'
                      }`}>
                        <Icon className={`w-5 h-5 ${isSelected ? 'text-emerald-600' : 'text-gray-500'}`} />
                      </div>
                      <div className="flex-1">
                        <h3 className="font-medium text-gray-900">{report.name}</h3>
                        <p className="text-sm text-gray-500 mt-0.5">{report.description}</p>
                      </div>
                      {reportLoading && isSelected && (
                        <RefreshCw className="w-4 h-4 animate-spin text-emerald-500" />
                      )}
                    </div>
                  </button>
                );
              })
            )}
          </div>

          {/* Report Results */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
              <div className="px-4 py-3 border-b bg-gray-50 flex items-center justify-between">
                <h2 className="font-semibold text-gray-900">
                  {reportResult?.report?.name || 'Kết quả báo cáo'}
                </h2>
                {reportResult?.results && (
                  <span className="text-xs text-gray-500">
                    {reportResult.row_count} dòng • {reportResult.execution_time_ms?.toFixed(1)}ms
                  </span>
                )}
              </div>
              
              {!reportResult ? (
                <div className="p-12 text-center text-gray-500">
                  <BarChart3 className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                  <p>Chọn một báo cáo để xem kết quả</p>
                </div>
              ) : reportResult.error ? (
                <div className="p-8 text-center text-red-500">
                  <AlertCircle className="w-10 h-10 mx-auto mb-2" />
                  <p>{reportResult.error}</p>
                </div>
              ) : (
                <div className="overflow-x-auto max-h-[500px]">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50 sticky top-0">
                      <tr>
                        {reportResult.results?.[0] && Object.keys(reportResult.results[0]).map((col) => (
                          <th key={col} className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                            {col.replace(/_/g, ' ')}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {reportResult.results?.slice(0, 100).map((row: any, idx: number) => (
                        <tr key={idx} className="hover:bg-gray-50">
                          {Object.values(row).map((val: any, colIdx: number) => (
                            <td key={colIdx} className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap">
                              {formatValue(val)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Tab: Data Analyze */}
      {activeTab === 'data' && (
        <div className="space-y-6">
          {/* Upload Section */}
          <div className="bg-white rounded-xl border shadow-sm p-6">
            <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Upload className="w-5 h-5 text-emerald-600" />
              Upload Dataset
            </h2>
            
            <div className="flex items-center gap-4">
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileSelect}
                accept=".csv,.xlsx,.xls"
                multiple
                className="hidden"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                className="flex items-center gap-2 px-4 py-2 border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-emerald-400 hover:text-emerald-600 transition-colors"
              >
                <FileSpreadsheet className="w-5 h-5" />
                Chọn file CSV/Excel
              </button>
              
              {uploadFiles.length > 0 && (
                <>
                  <div className="flex-1 flex flex-wrap gap-2">
                    {uploadFiles.map((f, i) => (
                      <span key={i} className="px-3 py-1 bg-emerald-50 text-emerald-700 rounded-full text-sm flex items-center gap-2">
                        {f.name}
                        <button onClick={() => setUploadFiles(prev => prev.filter((_, idx) => idx !== i))}>
                          <X className="w-3 h-3" />
                        </button>
                      </span>
                    ))}
                  </div>
                  <button
                    onClick={handleUpload}
                    disabled={uploading}
                    className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50"
                  >
                    {uploading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                    Upload
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Datasets List */}
          <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b bg-gray-50 flex items-center justify-between">
              <h2 className="font-semibold text-gray-900">Datasets</h2>
              <button onClick={() => refetchDatasets()} className="p-1.5 hover:bg-gray-200 rounded">
                <RefreshCw className={`w-4 h-4 text-gray-500 ${datasetsLoading ? 'animate-spin' : ''}`} />
              </button>
            </div>
            
            {datasets.length === 0 ? (
              <div className="p-8 text-center text-gray-500">
                <Database className="w-10 h-10 mx-auto mb-2 text-gray-300" />
                <p>Chưa có dataset nào</p>
                <p className="text-sm text-gray-400 mt-1">Upload CSV/Excel để bắt đầu</p>
              </div>
            ) : (
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Tên</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Số dòng</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Cột</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Ngày tạo</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Trạng thái</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {datasets.map((ds) => (
                    <tr key={ds.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">{ds.name}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{ds.row_count?.toLocaleString() || '-'}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{ds.columns?.length || '-'}</td>
                      <td className="px-4 py-3 text-sm text-gray-500">
                        {ds.created_at ? new Date(ds.created_at).toLocaleDateString('vi-VN') : '-'}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-1 text-xs rounded-full ${
                          ds.status === 'ready' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
                        }`}>
                          {ds.status || 'processing'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* NL2SQL Query */}
          <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
            <div className="p-4 border-b bg-gradient-to-r from-emerald-50 to-teal-50">
              <div className="flex items-start gap-3">
                <Sparkles className="w-5 h-5 text-emerald-600 mt-1" />
                <div className="flex-1">
                  <input
                    type="text"
                    value={queryText}
                    onChange={(e) => setQueryText(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleQuery()}
                    placeholder="Hỏi về dữ liệu, VD: 'Tổng doanh thu theo nhà cung cấp'..."
                    className="w-full bg-white border rounded-lg px-4 py-3 focus:ring-2 focus:ring-emerald-500"
                  />
                  <div className="flex items-center justify-between mt-3">
                    <div className="flex gap-2">
                      {['Tổng doanh thu tháng này', 'Top 10 nhà cung cấp'].map((q, i) => (
                        <button
                          key={i}
                          onClick={() => setQueryText(q)}
                          className="text-xs px-2 py-1 bg-white border rounded-full hover:bg-emerald-50"
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                    <button
                      onClick={handleQuery}
                      disabled={!queryText.trim() || queryMutation.isPending}
                      className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50"
                    >
                      {queryMutation.isPending ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                      Truy vấn
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Query Results */}
            {queryResult && (
              <div className="p-4">
                {queryResult.error ? (
                  <div className="text-red-500 flex items-center gap-2">
                    <AlertCircle className="w-5 h-5" />
                    {queryResult.error}
                  </div>
                ) : (
                  <>
                    <div className="flex items-center gap-4 mb-4 text-sm text-gray-600">
                      <span>{queryResult.row_count} kết quả</span>
                      <span>•</span>
                      <span>{queryResult.execution_time_ms?.toFixed(1)}ms</span>
                    </div>
                    <div className="overflow-x-auto max-h-80">
                      <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                          <tr>
                            {queryResult.columns?.map((col: string) => (
                              <th key={col} className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase">
                                {col}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {queryResult.rows?.slice(0, 50).map((row: any, idx: number) => (
                            <tr key={idx} className="hover:bg-gray-50">
                              {queryResult.columns?.map((col: string) => (
                                <td key={col} className="px-4 py-2 text-sm text-gray-700">
                                  {formatValue(row[col])}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
