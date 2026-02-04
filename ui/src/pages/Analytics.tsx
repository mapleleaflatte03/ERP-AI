/**
 * Analytics Module v3.0 - Complete Redesign
 * Modern AI-powered financial analysis dashboard
 * Note: Chat functionality is provided by ModuleChatDock component
 */

import { useState, useRef } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Database,
  TrendingUp,
  FileSpreadsheet,
  Play,
  Sparkles,
  ArrowUp,
  ArrowDown,
  Table,
  Upload,
  X,
  Users,
  DollarSign,
  FileText,
  Download,
  Eye,
  Trash2,
  LayoutDashboard,
  Activity,
  Zap,
  Loader2,
  Hash,
  Layers,
  Settings,
  MoreVertical,
} from 'lucide-react';
import ModuleChatDock from '../components/moduleChat/ModuleChatDock';

// Types
interface Dataset {
  name: string;
  row_count: number;
  column_count: number;
  columns?: string[];
  description?: string;
}

type TabType = 'dashboard' | 'explorer' | 'forecast' | 'datasets';

const formatNumber = (num: number) => {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
  return num.toLocaleString();
};

const formatCurrency = (num: number) => {
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(num);
};

// ============================================================
// MAIN COMPONENT
// ============================================================
export default function Analytics() {
  const [activeTab, setActiveTab] = useState<TabType>('dashboard');

  const tabs = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'explorer', label: 'Explorer', icon: Database },
    { id: 'forecast', label: 'Dự báo', icon: TrendingUp },
    { id: 'datasets', label: 'Datasets', icon: FileSpreadsheet },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-violet-50">
      {/* Header */}
      <div className="bg-white/80 backdrop-blur-lg border-b border-gray-200/50 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="relative">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-violet-600 via-purple-600 to-indigo-600 flex items-center justify-center shadow-xl shadow-violet-500/30">
                  <Sparkles className="w-7 h-7 text-white" />
                </div>
                <div className="absolute -bottom-1 -right-1 w-5 h-5 bg-green-500 rounded-full border-2 border-white flex items-center justify-center">
                  <span className="text-[8px] text-white font-bold">AI</span>
                </div>
              </div>
              <div>
                <h1 className="text-2xl font-bold bg-gradient-to-r from-gray-900 via-violet-900 to-purple-900 bg-clip-text text-transparent">
                  Analytics Studio
                </h1>
                <p className="text-sm text-gray-500">Phân tích dữ liệu thông minh với AI</p>
              </div>
            </div>
            
            {/* Quick Stats */}
            <div className="hidden md:flex items-center gap-4">
              <QuickStat icon={Database} label="Datasets" value="4" trend="+2" />
              <QuickStat icon={Activity} label="Queries" value="156" trend="+23%" />
              <QuickStat icon={Zap} label="AI Calls" value="89" trend="+15%" />
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 mt-6 bg-gray-100/80 p-1.5 rounded-2xl w-fit">
            {tabs.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id as TabType)}
                className={`relative px-5 py-2.5 rounded-xl font-medium text-sm transition-all duration-300 flex items-center gap-2 ${
                  activeTab === id
                    ? 'bg-white text-violet-700 shadow-lg shadow-violet-500/10'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                <Icon className="w-4 h-4" />
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-6 py-6">
        {activeTab === 'dashboard' && <DashboardTab />}
        {activeTab === 'explorer' && <ExplorerTab />}
        {activeTab === 'forecast' && <ForecastTab />}
        {activeTab === 'datasets' && <DatasetsTab />}
      </div>
      <ModuleChatDock module="analyze" />
    </div>
  );
}

// Quick Stat Component
function QuickStat({ icon: Icon, label, value, trend }: { icon: any; label: string; value: string; trend: string }) {
  return (
    <div className="flex items-center gap-3 px-4 py-2 bg-gray-50 rounded-xl">
      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-100 to-purple-100 flex items-center justify-center">
        <Icon className="w-5 h-5 text-violet-600" />
      </div>
      <div>
        <p className="text-xs text-gray-500">{label}</p>
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold text-gray-900">{value}</span>
          <span className="text-xs text-emerald-600 font-medium">{trend}</span>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// DASHBOARD TAB
// ============================================================
function DashboardTab() {
  const { data: kpis, isLoading: kpisLoading } = useQuery({
    queryKey: ['analytics-kpis'],
    queryFn: async () => {
      const res = await fetch('/v1/analytics/kpis');
      return res.json();
    },
  });

  const { data: datasets } = useQuery({
    queryKey: ['analytics-datasets'],
    queryFn: async () => {
      const res = await fetch('/v1/analyze/datasets');
      return res.json();
    },
  });

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Tổng doanh thu', value: kpis?.metrics?.total_revenue?.value || 125000000, icon: DollarSign, color: 'emerald', change: 12.5 },
          { label: 'Chi phí', value: kpis?.metrics?.total_expenses?.value || 45000000, icon: FileText, color: 'red', change: -5.2 },
          { label: 'Lợi nhuận ròng', value: kpis?.metrics?.net_profit?.value || 80000000, icon: TrendingUp, color: 'blue', change: 18.3 },
          { label: 'Khách hàng', value: kpis?.metrics?.customer_count?.value || 1250, icon: Users, color: 'violet', change: 8.1 },
        ].map((kpi, i) => (
          <KPICard key={i} {...kpi} loading={kpisLoading} />
        ))}
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chart Area */}
        <div className="lg:col-span-2 bg-white rounded-3xl border border-gray-200/50 shadow-xl shadow-gray-200/50 p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-lg font-bold text-gray-900">Xu hướng doanh thu</h3>
              <p className="text-sm text-gray-500">7 ngày gần nhất</p>
            </div>
            <div className="flex gap-2">
              <button className="px-3 py-1.5 text-xs font-medium bg-violet-100 text-violet-700 rounded-lg">7D</button>
              <button className="px-3 py-1.5 text-xs font-medium text-gray-500 hover:bg-gray-100 rounded-lg">30D</button>
              <button className="px-3 py-1.5 text-xs font-medium text-gray-500 hover:bg-gray-100 rounded-lg">90D</button>
            </div>
          </div>
          
          {/* Simple Chart Placeholder */}
          <div className="h-64 flex items-end gap-2 px-4">
            {[65, 78, 52, 90, 85, 92, 88].map((h, i) => (
              <div key={i} className="flex-1 flex flex-col items-center gap-2">
                <div 
                  className="w-full bg-gradient-to-t from-violet-500 to-purple-400 rounded-t-lg transition-all duration-500"
                  style={{ height: `${h}%` }}
                />
                <span className="text-xs text-gray-400">{['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'][i]}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Datasets Panel */}
        <div className="bg-white rounded-3xl border border-gray-200/50 shadow-xl shadow-gray-200/50 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-gray-900">Datasets</h3>
            <span className="px-3 py-1 bg-violet-100 text-violet-700 text-xs font-bold rounded-full">
              {datasets?.total || 0}
            </span>
          </div>
          <div className="space-y-3">
            {datasets?.datasets?.slice(0, 5).map((ds: Dataset) => (
              <div
                key={ds.name}
                className="group flex items-center gap-3 p-3 rounded-2xl hover:bg-gray-50 transition-all cursor-pointer"
              >
                <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-lg shadow-violet-500/30">
                  <FileSpreadsheet className="w-5 h-5 text-white" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-gray-900 truncate">{ds.name}</p>
                  <p className="text-xs text-gray-500">{ds.column_count} cột</p>
                </div>
                <div className="text-right">
                  <p className="font-bold text-violet-600">{formatNumber(ds.row_count)}</p>
                  <p className="text-xs text-gray-400">rows</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* AI Banner */}
      <div className="relative overflow-hidden bg-gradient-to-r from-violet-600 via-purple-600 to-indigo-600 rounded-3xl p-8">
        <div className="absolute top-0 right-0 w-96 h-96 bg-white/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
        <div className="relative flex items-center gap-6">
          <div className="w-16 h-16 rounded-2xl bg-white/20 backdrop-blur flex items-center justify-center">
            <Sparkles className="w-8 h-8 text-white" />
          </div>
          <div className="flex-1">
            <h3 className="text-xl font-bold text-white mb-1">Hỏi AI bất cứ điều gì</h3>
            <p className="text-white/70 text-sm">
              "Phân tích xu hướng doanh thu", "So sánh các sản phẩm", "Dự báo 30 ngày tới"...
            </p>
          </div>
          <button 
            onClick={() => {}}
            className="px-6 py-3 bg-white text-violet-600 rounded-xl font-semibold hover:bg-gray-100 transition-colors shadow-lg"
          >
            Bắt đầu Chat
          </button>
        </div>
      </div>
    </div>
  );
}

function KPICard({ label, value, icon: Icon, color, change, loading }: any) {
  const colors: Record<string, { bg: string; text: string; shadow: string }> = {
    emerald: { bg: 'from-emerald-500 to-teal-500', text: 'text-emerald-600', shadow: 'shadow-emerald-500/30' },
    red: { bg: 'from-red-500 to-rose-500', text: 'text-red-600', shadow: 'shadow-red-500/30' },
    blue: { bg: 'from-blue-500 to-indigo-500', text: 'text-blue-600', shadow: 'shadow-blue-500/30' },
    violet: { bg: 'from-violet-500 to-purple-500', text: 'text-violet-600', shadow: 'shadow-violet-500/30' },
  };
  const c = colors[color] || colors.violet;

  return (
    <div className="bg-white rounded-3xl border border-gray-200/50 shadow-xl shadow-gray-200/50 p-6 hover:shadow-2xl transition-shadow">
      <div className="flex items-start justify-between mb-4">
        <div className={`w-12 h-12 rounded-2xl bg-gradient-to-br ${c.bg} flex items-center justify-center shadow-lg ${c.shadow}`}>
          <Icon className="w-6 h-6 text-white" />
        </div>
        <div className={`flex items-center gap-1 text-sm font-semibold ${change >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
          {change >= 0 ? <ArrowUp className="w-4 h-4" /> : <ArrowDown className="w-4 h-4" />}
          {Math.abs(change)}%
        </div>
      </div>
      <p className="text-sm text-gray-500 mb-1">{label}</p>
      {loading ? (
        <div className="h-8 w-32 bg-gray-200 animate-pulse rounded-lg" />
      ) : (
        <p className="text-2xl font-bold text-gray-900">
          {typeof value === 'number' && value > 10000 ? formatCurrency(value) : formatNumber(value)}
        </p>
      )}
    </div>
  );
}

// ============================================================
// EXPLORER TAB
// ============================================================
function ExplorerTab() {
  const [query, setQuery] = useState('SELECT * FROM transactions LIMIT 10');
  const [queryResult, setQueryResult] = useState<any>(null);

  const { data: schema } = useQuery({
    queryKey: ['analytics-schema'],
    queryFn: async () => {
      const res = await fetch('/v1/analytics/schema');
      return res.json();
    },
  });

  const queryMutation = useMutation({
    mutationFn: async (sql: string) => {
      const res = await fetch('/v1/analytics/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: sql, execute: true }),
      });
      return res.json();
    },
    onSuccess: setQueryResult,
  });

  return (
    <div className="grid grid-cols-4 gap-6" style={{ height: 'calc(100vh - 220px)' }}>
      {/* Schema Sidebar */}
      <div className="bg-white rounded-3xl border border-gray-200/50 shadow-xl shadow-gray-200/50 p-5 overflow-y-auto">
        <h3 className="font-bold text-gray-900 mb-4 flex items-center gap-2">
          <Database className="w-5 h-5 text-violet-600" />
          Schema
        </h3>
        <div className="space-y-3">
          {schema?.tables?.map((table: any) => (
            <div key={table.name} className="bg-gray-50 rounded-xl p-3">
              <div className="flex items-center gap-2 mb-2">
                <Table className="w-4 h-4 text-violet-600" />
                <span className="font-semibold text-gray-900 text-sm">{table.name}</span>
              </div>
              {table.columns?.slice(0, 4).map((col: any) => (
                <div key={col.name} className="flex items-center gap-2 text-xs text-gray-500 pl-6 py-0.5">
                  <Hash className="w-3 h-3" />
                  <span>{col.name}</span>
                  <span className="ml-auto text-gray-400">{col.type}</span>
                </div>
              ))}
              {table.columns?.length > 4 && (
                <p className="text-xs text-gray-400 pl-6">+{table.columns.length - 4} more</p>
              )}
            </div>
          )) || <p className="text-sm text-gray-500">Loading...</p>}
        </div>
      </div>

      {/* Query Editor & Results */}
      <div className="col-span-3 flex flex-col gap-4">
        <div className="bg-white rounded-3xl border border-gray-200/50 shadow-xl shadow-gray-200/50 p-5">
          <div className="flex gap-3">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 p-4 bg-gray-50 border-0 rounded-xl font-mono text-sm resize-none focus:outline-none focus:ring-2 focus:ring-violet-500"
              rows={3}
              placeholder="SELECT * FROM ..."
            />
            <button
              onClick={() => queryMutation.mutate(query)}
              disabled={queryMutation.isPending}
              className="px-6 bg-gradient-to-r from-emerald-500 to-teal-500 text-white rounded-xl font-semibold hover:opacity-90 disabled:opacity-50 flex items-center gap-2 shadow-lg shadow-emerald-500/30"
            >
              {queryMutation.isPending ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5" />}
              Run
            </button>
          </div>
        </div>

        <div className="flex-1 bg-white rounded-3xl border border-gray-200/50 shadow-xl shadow-gray-200/50 p-5 overflow-auto">
          {queryResult?.results ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  {Object.keys(queryResult.results[0] || {}).map((col) => (
                    <th key={col} className="px-4 py-3 text-left font-semibold text-gray-700 bg-gray-50">{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {queryResult.results.map((row: any, i: number) => (
                  <tr key={i} className="border-b hover:bg-gray-50">
                    {Object.values(row).map((val: any, j: number) => (
                      <td key={j} className="px-4 py-3 text-gray-600">{String(val)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="h-full flex items-center justify-center text-gray-400">
              <div className="text-center">
                <Database className="w-16 h-16 mx-auto mb-3 opacity-30" />
                <p>Run a query to see results</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================
// FORECAST TAB
// ============================================================
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
    <div className="space-y-6">
      {/* Config */}
      <div className="bg-white rounded-3xl border border-gray-200/50 shadow-xl shadow-gray-200/50 p-6">
        <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
          <Settings className="w-5 h-5 text-violet-600" />
          Cấu hình dự báo
        </h3>
        <div className="grid grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Chỉ số</label>
            <select value={metric} onChange={(e) => setMetric(e.target.value)} className="w-full p-3 bg-gray-50 border-0 rounded-xl focus:ring-2 focus:ring-violet-500">
              <option value="revenue">Doanh thu</option>
              <option value="expenses">Chi phí</option>
              <option value="profit">Lợi nhuận</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Số ngày</label>
            <input type="number" value={horizon} onChange={(e) => setHorizon(+e.target.value)} min={7} max={365} className="w-full p-3 bg-gray-50 border-0 rounded-xl focus:ring-2 focus:ring-violet-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Mô hình</label>
            <select value={model} onChange={(e) => setModel(e.target.value)} className="w-full p-3 bg-gray-50 border-0 rounded-xl focus:ring-2 focus:ring-violet-500">
              <option value="linear">Linear</option>
              <option value="prophet">Prophet</option>
              <option value="arima">ARIMA</option>
            </select>
          </div>
          <div className="flex items-end">
            <button onClick={() => forecastMutation.mutate()} disabled={forecastMutation.isPending} className="w-full px-6 py-3 bg-gradient-to-r from-orange-500 to-red-500 text-white rounded-xl font-semibold hover:opacity-90 disabled:opacity-50 flex items-center justify-center gap-2 shadow-lg shadow-orange-500/30">
              {forecastMutation.isPending ? <Loader2 className="w-5 h-5 animate-spin" /> : <TrendingUp className="w-5 h-5" />}
              Dự báo
            </button>
          </div>
        </div>
      </div>

      {/* Results */}
      {forecastMutation.data ? (
        <div className="bg-white rounded-3xl border border-gray-200/50 shadow-xl shadow-gray-200/50 p-6">
          <h3 className="text-lg font-bold text-gray-900 mb-4">Kết quả dự báo</h3>
          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-2xl p-5">
              <p className="text-sm text-gray-600 mb-1">Dự báo TB</p>
              <p className="text-2xl font-bold text-blue-600">{formatCurrency(forecastMutation.data.summary?.mean || 0)}</p>
            </div>
            <div className="bg-gradient-to-br from-emerald-50 to-teal-50 rounded-2xl p-5">
              <p className="text-sm text-gray-600 mb-1">Tăng trưởng</p>
              <p className="text-2xl font-bold text-emerald-600">+{(forecastMutation.data.summary?.growth || 0).toFixed(1)}%</p>
            </div>
            <div className="bg-gradient-to-br from-violet-50 to-purple-50 rounded-2xl p-5">
              <p className="text-sm text-gray-600 mb-1">Độ tin cậy</p>
              <p className="text-2xl font-bold text-violet-600">{forecastMutation.data.summary?.confidence || 95}%</p>
            </div>
          </div>
          <div className="overflow-auto max-h-64">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold text-gray-700">Ngày</th>
                  <th className="px-4 py-3 text-right font-semibold text-gray-700">Dự báo</th>
                  <th className="px-4 py-3 text-right font-semibold text-gray-700">Khoảng tin cậy</th>
                </tr>
              </thead>
              <tbody>
                {forecastMutation.data.forecast?.slice(0, 10).map((f: any, i: number) => (
                  <tr key={i} className="border-b">
                    <td className="px-4 py-3">{f.date || f.ds}</td>
                    <td className="px-4 py-3 text-right font-medium">{formatCurrency(f.yhat || f.value)}</td>
                    <td className="px-4 py-3 text-right text-gray-500 text-xs">{formatCurrency(f.yhat_lower || f.lower)} - {formatCurrency(f.yhat_upper || f.upper)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : !forecastMutation.isPending && (
        <div className="bg-white rounded-3xl border border-gray-200/50 shadow-xl shadow-gray-200/50 p-12 text-center">
          <TrendingUp className="w-20 h-20 mx-auto mb-4 text-gray-200" />
          <p className="text-gray-500">Chọn cấu hình và nhấn "Dự báo"</p>
        </div>
      )}
    </div>
  );
}

// ============================================================
// DATASETS TAB
// ============================================================
function DatasetsTab() {
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [selected, setSelected] = useState<Dataset | null>(null);
  const [previewData, setPreviewData] = useState<any>(null);
  const [showPreview, setShowPreview] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['analytics-datasets'],
    queryFn: async () => {
      const res = await fetch('/v1/analyze/datasets');
      return res.json();
    },
  });

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('name', file.name.replace(/\.[^/.]+$/, ''));
      const res = await fetch('/v1/analyze/datasets/upload', { method: 'POST', body: formData });
      if (!res.ok) throw new Error('Upload failed');
      return res.json();
    },
    onSuccess: () => { 
      setUploadFiles([]); 
      refetch(); 
      alert('✅ Upload thành công!');
    },
    onError: (err) => alert(`❌ Upload thất bại: ${err}`),
  });

  const previewMutation = useMutation({
    mutationFn: async (datasetId: string) => {
      const res = await fetch(`/v1/analyze/datasets/${datasetId}/preview?limit=200`);
      if (!res.ok) throw new Error('Preview failed');
      return res.json();
    },
    onSuccess: (data) => {
      setPreviewData(data);
      setShowPreview(true);
    },
    onError: (err) => alert(`❌ Preview thất bại: ${err}`),
  });

  const cleanMutation = useMutation({
    mutationFn: async (datasetId: string) => {
      const res = await fetch(`/v1/analyze/datasets/${datasetId}/clean`, { method: 'POST' });
      if (!res.ok) throw new Error('Clean failed');
      return res.json();
    },
    onSuccess: (data) => {
      refetch();
      alert(`✅ Clean thành công! Đã xử lý ${data.cleaned_rows} rows (xóa ${data.rows_removed} rows rỗng)`);
    },
    onError: (err) => alert(`❌ Clean thất bại: ${err}`),
  });

  const deleteMutation = useMutation({
    mutationFn: async (datasetId: string) => {
      const res = await fetch(`/v1/analyze/datasets/${datasetId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Delete failed');
      return res.json();
    },
    onSuccess: () => {
      setSelected(null);
      refetch();
      alert('✅ Xóa thành công!');
    },
    onError: (err) => alert(`❌ Xóa thất bại: ${err}`),
  });

  const handleExport = async (datasetId: string, name: string) => {
    try {
      const res = await fetch(`/v1/analyze/datasets/${datasetId}/export`);
      if (!res.ok) throw new Error('Export failed');
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${name}.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert(`❌ Export thất bại: ${err}`);
    }
  };

  // Get dataset ID from data (might be 'id' or need to find by name)
  const getDatasetId = (ds: Dataset): string => {
    // Check if data.datasets has id field
    const found = data?.datasets?.find((d: any) => d.name === ds.name);
    return found?.id || ds.name;
  };

  return (
    <div className="flex gap-6" style={{ height: 'calc(100vh - 220px)' }}>
      {/* Preview Modal */}
      {showPreview && previewData && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShowPreview(false)}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-5xl max-h-[80vh] overflow-hidden" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="font-bold text-lg">Preview ({previewData.preview_rows} / {previewData.total_rows} rows)</h3>
              <button onClick={() => setShowPreview(false)} className="p-2 hover:bg-gray-100 rounded-lg"><X className="w-5 h-5" /></button>
            </div>
            <div className="overflow-auto max-h-[calc(80vh-80px)]">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    {previewData.columns?.map((col: any, i: number) => (
                      <th key={i} className="px-4 py-3 text-left font-medium text-gray-700 border-b">{col.name || col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {previewData.data?.map((row: any, i: number) => (
                    <tr key={i} className="hover:bg-gray-50">
                      {Object.values(row).map((val: any, j: number) => (
                        <td key={j} className="px-4 py-2 border-b text-gray-600">{String(val ?? '')}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Main */}
      <div className="flex-1 overflow-y-auto">
        {/* Upload */}
        <div
          onClick={() => fileInputRef.current?.click()}
          className="border-2 border-dashed border-gray-300 rounded-3xl p-10 mb-6 hover:border-violet-400 hover:bg-violet-50/30 transition-all cursor-pointer text-center"
        >
          <input ref={fileInputRef} type="file" onChange={(e) => setUploadFiles(Array.from(e.target.files || []))} accept=".csv,.xlsx,.xls" multiple className="hidden" />
          <div className="w-16 h-16 rounded-2xl bg-violet-100 flex items-center justify-center mx-auto mb-4">
            <Upload className="w-8 h-8 text-violet-600" />
          </div>
          <h3 className="text-lg font-bold text-gray-900 mb-1">Kéo thả hoặc click để upload</h3>
          <p className="text-gray-500 text-sm">CSV, Excel (.xlsx, .xls)</p>
          
          {uploadFiles.length > 0 && (
            <div className="mt-4 pt-4 border-t flex flex-wrap gap-2 justify-center">
              {uploadFiles.map((f, i) => (
                <span key={i} className="px-4 py-2 bg-violet-100 text-violet-700 rounded-full text-sm flex items-center gap-2">
                  <FileSpreadsheet className="w-4 h-4" /> {f.name}
                  <button onClick={(e) => { e.stopPropagation(); setUploadFiles((p) => p.filter((_, idx) => idx !== i)); }}>
                    <X className="w-4 h-4" />
                  </button>
                </span>
              ))}
              <button onClick={(e) => { e.stopPropagation(); uploadFiles.forEach((f) => uploadMutation.mutate(f)); }} disabled={uploadMutation.isPending} className="px-5 py-2 bg-violet-600 text-white rounded-full text-sm font-medium flex items-center gap-2">
                {uploadMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />} Upload
              </button>
            </div>
          )}
        </div>

        {/* Grid */}
        <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
          <Layers className="w-5 h-5 text-violet-600" />
          Datasets ({data?.total || 0})
        </h3>

        {isLoading ? (
          <div className="grid grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="bg-white rounded-2xl border p-5 animate-pulse">
                <div className="w-12 h-12 bg-gray-200 rounded-xl mb-4" />
                <div className="h-5 bg-gray-200 rounded w-3/4 mb-2" />
                <div className="h-4 bg-gray-200 rounded w-1/2" />
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-4">
            {data?.datasets?.map((ds: any) => (
              <div
                key={ds.id || ds.name}
                onClick={() => setSelected(ds)}
                className={`bg-white rounded-2xl border p-5 cursor-pointer transition-all hover:shadow-xl hover:border-violet-300 ${selected?.name === ds.name ? 'border-violet-500 ring-2 ring-violet-200' : ''}`}
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-lg shadow-violet-500/30">
                    <FileSpreadsheet className="w-6 h-6 text-white" />
                  </div>
                  <div className="flex items-center gap-1">
                    {ds.status === 'cleaned' && (
                      <span className="px-2 py-1 bg-green-100 text-green-700 text-xs rounded-full">Cleaned</span>
                    )}
                    <button className="p-2 hover:bg-gray-100 rounded-lg"><MoreVertical className="w-4 h-4 text-gray-400" /></button>
                  </div>
                </div>
                <h4 className="font-bold text-gray-900 truncate">{ds.name}</h4>
                <p className="text-sm text-gray-500 mb-3">{ds.description || 'No description'}</p>
                <div className="flex gap-4 text-sm">
                  <span className="flex items-center gap-1 text-gray-600"><Hash className="w-4 h-4 text-gray-400" /> <strong>{formatNumber(ds.row_count || 0)}</strong> rows</span>
                  <span className="flex items-center gap-1 text-gray-600"><Layers className="w-4 h-4 text-gray-400" /> <strong>{ds.column_count || 0}</strong> cols</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Detail Panel */}
      {selected && (
        <div className="w-80 bg-white rounded-3xl border border-gray-200/50 shadow-xl shadow-gray-200/50 p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="font-bold text-gray-900">Chi tiết</h3>
            <button onClick={() => setSelected(null)} className="p-2 hover:bg-gray-100 rounded-lg"><X className="w-4 h-4" /></button>
          </div>
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center mb-4 shadow-lg shadow-violet-500/30">
            <FileSpreadsheet className="w-8 h-8 text-white" />
          </div>
          <h4 className="text-xl font-bold text-gray-900 mb-2">{selected.name}</h4>
          <p className="text-gray-500 text-sm mb-6">{selected.description || 'Không có mô tả'}</p>
          <div className="space-y-3 mb-6">
            <div className="flex justify-between py-2 border-b"><span className="text-gray-500">Rows</span><span className="font-bold">{formatNumber(selected.row_count || 0)}</span></div>
            <div className="flex justify-between py-2 border-b"><span className="text-gray-500">Columns</span><span className="font-bold">{selected.column_count || 0}</span></div>
            <div className="flex justify-between py-2 border-b">
              <span className="text-gray-500">Status</span>
              <span className={`font-bold ${(selected as any).status === 'cleaned' ? 'text-green-600' : 'text-amber-600'}`}>
                {(selected as any).status || 'raw'}
              </span>
            </div>
          </div>
          <div className="space-y-2">
            <button 
              onClick={() => previewMutation.mutate(getDatasetId(selected))}
              disabled={previewMutation.isPending}
              className="w-full px-4 py-3 bg-violet-100 text-violet-700 rounded-xl font-medium flex items-center justify-center gap-2 hover:bg-violet-200 disabled:opacity-50"
            >
              {previewMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />} Xem dữ liệu
            </button>
            <button 
              onClick={() => cleanMutation.mutate(getDatasetId(selected))}
              disabled={cleanMutation.isPending || (selected as any).status === 'cleaned'}
              className="w-full px-4 py-3 bg-blue-100 text-blue-700 rounded-xl font-medium flex items-center justify-center gap-2 hover:bg-blue-200 disabled:opacity-50"
            >
              {cleanMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />} 
              {(selected as any).status === 'cleaned' ? 'Đã Clean' : 'Clean Data'}
            </button>
            <button 
              onClick={() => handleExport(getDatasetId(selected), selected.name)}
              className="w-full px-4 py-3 bg-gray-100 text-gray-700 rounded-xl font-medium flex items-center justify-center gap-2 hover:bg-gray-200"
            >
              <Download className="w-4 h-4" /> Export CSV
            </button>
            <button 
              onClick={() => {
                if (confirm(`Xóa dataset "${selected.name}"?`)) {
                  deleteMutation.mutate(getDatasetId(selected));
                }
              }}
              disabled={deleteMutation.isPending}
              className="w-full px-4 py-3 bg-red-50 text-red-600 rounded-xl font-medium flex items-center justify-center gap-2 hover:bg-red-100 disabled:opacity-50"
            >
              {deleteMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />} Xóa
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
