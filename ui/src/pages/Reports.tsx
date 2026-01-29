import { useState } from 'react';
import {
  FileText,
  TrendingUp,
  DollarSign,
  PieChart,
  BarChart3,
  Download,
  RefreshCw,
  ArrowRight,
  HelpCircle,
  Lock,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

const REPORTS = [
  {
    id: 'balance_sheet',
    name: 'Bảng cân đối kế toán',
    description: 'Tài sản, Nợ phải trả, Vốn chủ sở hữu',
    icon: PieChart,
    available: false,
  },
  {
    id: 'income_statement',
    name: 'Báo cáo kết quả kinh doanh',
    description: 'Doanh thu, Chi phí, Lợi nhuận',
    icon: BarChart3,
    available: false,
  },
  {
    id: 'cashflow',
    name: 'Báo cáo lưu chuyển tiền tệ',
    description: 'Dòng tiền hoạt động, đầu tư, tài chính',
    icon: DollarSign,
    available: false,
  },
  {
    id: 'general_ledger',
    name: 'Sổ cái tổng hợp',
    description: 'Tổng hợp các tài khoản kế toán',
    icon: FileText,
    available: true,
  },
  {
    id: 'trial_balance',
    name: 'Bảng cân đối phát sinh',
    description: 'Số dư đầu kỳ, Phát sinh, Số dư cuối kỳ',
    icon: BarChart3,
    available: true,
  },
  {
    id: 'cashflow_forecast',
    name: 'Dự báo dòng tiền',
    description: 'Dự đoán dòng tiền 30/60/90 ngày',
    icon: TrendingUp,
    available: false,
  },
];


import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';

function formatCurrency(val: number) {
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(val);
}


export default function Reports() {
  const [selectedReport, setSelectedReport] = useState<string | null>('general_ledger');
  const [dateRange, setDateRange] = useState({ from: '2025-01-01', to: '2025-12-31' }); // Default to current year or broad range

  const { data: reportData, isLoading, refetch } = useQuery({
    queryKey: ['report-gl', dateRange.from, dateRange.to],
    queryFn: () => api.getGeneralLedger(dateRange.from, dateRange.to),
    enabled: false, // Wait for button
  });

  const { data: chartData } = useQuery({
    queryKey: ['report-timeseries', dateRange.from, dateRange.to],
    queryFn: () => api.getReportTimeseries(dateRange.from, dateRange.to),
    enabled: !!selectedReport, // Auto load for charts
  });

  const handleGenerate = () => {
    refetch();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Báo cáo</h1>
          <p className="text-gray-500 text-sm mt-1">Báo cáo tài chính và phân tích</p>
        </div>
      </div>

      {/* Reports Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {REPORTS.map(report => (
          <button
            key={report.id}
            onClick={() => report.available && setSelectedReport(report.id)}
            disabled={!report.available}
            className={`relative text-left p-4 rounded-xl border transition-all ${selectedReport === report.id
              ? 'bg-blue-50 border-blue-300 ring-2 ring-blue-500'
              : report.available
                ? 'bg-white hover:bg-gray-50 hover:border-gray-300'
                : 'bg-gray-50 opacity-60 cursor-not-allowed'
              }`}
          >
            {/* ... same icon logic ... */}
            {!report.available && (
              <div className="absolute top-2 right-2">
                <Lock className="w-4 h-4 text-gray-400" />
              </div>
            )}
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center mb-3 ${selectedReport === report.id ? 'bg-blue-100' : 'bg-gray-100'
              }`}>
              <report.icon className={`w-5 h-5 ${selectedReport === report.id ? 'text-blue-600' : 'text-gray-500'
                }`} />
            </div>
            <h3 className="font-medium text-gray-900">{report.name}</h3>
            <p className="text-sm text-gray-500 mt-1">{report.description}</p>
            {!report.available && (
              <span className="inline-block mt-2 px-2 py-0.5 bg-gray-200 text-gray-600 rounded text-xs">
                Coming soon
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Report Parameters */}
      {selectedReport && (
        <div className="bg-white rounded-xl border shadow-sm p-4">
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Từ ngày</label>
              <input
                type="date"
                value={dateRange.from}
                onChange={e => setDateRange(prev => ({ ...prev, from: e.target.value }))}
                className="px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Đến ngày</label>
              <input
                type="date"
                value={dateRange.to}
                onChange={e => setDateRange(prev => ({ ...prev, to: e.target.value }))}
                className="px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <button
              onClick={handleGenerate}
              disabled={isLoading}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {isLoading ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4" />
              )}
              Tạo báo cáo
            </button>
            <button className="flex items-center gap-2 px-4 py-2 border rounded-lg hover:bg-gray-50">
              <Download className="w-4 h-4" />
              Xuất Excel
            </button>
          </div>
        </div>
      )}

      {/* Report Content */}
      {selectedReport === 'general_ledger' && (
        <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b bg-gray-50 flex items-center justify-between">
            <h2 className="font-semibold text-gray-900">Sổ cái tổng hợp</h2>
            <span className="text-sm text-gray-500">
              Kỳ: {dateRange.from} - {dateRange.to}
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mã TK</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tên tài khoản</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Dư đầu kỳ</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">PS Nợ</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">PS Có</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Dư cuối kỳ</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {!reportData?.entries || reportData.entries.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                      <FileText className="w-10 h-10 mx-auto text-gray-300 mb-3" />
                      <p>{isLoading ? 'Đang tải...' : 'Chưa có dữ liệu sổ cái'}</p>
                      {!isLoading && <p className="text-sm text-gray-400 mt-1">Dữ liệu sẽ hiển thị khi có bút toán đã ghi sổ trong kỳ này</p>}
                    </td>
                  </tr>
                ) : (
                  reportData.entries.map((row: any) => (
                    <tr key={row.account_code} className="hover:bg-gray-50">
                      <td className="px-4 py-3 font-mono font-medium text-blue-600">{row.account_code}</td>
                      <td className="px-4 py-3 text-gray-900">{row.account_name}</td>
                      <td className="px-4 py-3 text-right font-mono text-gray-600">{formatCurrency(row.opening_balance)}</td>
                      <td className="px-4 py-3 text-right font-mono text-gray-600">{formatCurrency(row.debit)}</td>
                      <td className="px-4 py-3 text-right font-mono text-gray-600">{formatCurrency(row.credit)}</td>
                      <td className="px-4 py-3 text-right font-mono font-medium text-gray-900">{formatCurrency(row.closing_balance)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {selectedReport === 'trial_balance' && (
        <div className="bg-white rounded-xl border shadow-sm overflow-hidden p-6">
          <div className="border-b pb-4 mb-4 flex justify-between items-center">
            <h2 className="font-semibold text-gray-900">Doanh thu & Chi phí (Theo thời gian)</h2>
          </div>

          <div className="h-[400px] w-full">
            {!chartData ? (
              <div className="h-full flex items-center justify-center text-gray-400">Loading chart data...</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={chartData.labels.map((label: string, i: number) => ({
                    name: label,
                    revenue: chartData.datasets[0].data[i],
                    expense: chartData.datasets[1].data[i],
                  }))}
                  margin={{
                    top: 20,
                    right: 30,
                    left: 20,
                    bottom: 5,
                  }}
                >
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" />
                  <YAxis tickFormatter={(val) => new Intl.NumberFormat('en', { notation: "compact" }).format(val)} />
                  <Tooltip
                    formatter={(value: any) => new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(Number(value || 0))}
                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                  />
                  <Legend />
                  <Bar dataKey="revenue" name="Doanh thu" fill="#10b981" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="expense" name="Chi phí" fill="#ef4444" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      )}

      {/* Coming Soon Notice */}
      <div className="bg-gradient-to-r from-purple-50 to-pink-50 border border-purple-200 rounded-xl p-6">
        {/* ... same ... */}
        <h3 className="font-semibold text-purple-900 flex items-center gap-2">
          <HelpCircle className="w-5 h-5" />
          Tính năng đang phát triển
        </h3>
        <ul className="mt-3 text-sm text-purple-700 space-y-2">
          <li className="flex items-start gap-2">
            <ArrowRight className="w-4 h-4 mt-0.5 flex-shrink-0" />
            Bảng cân đối kế toán theo Thông tư 200/2014/TT-BTC
          </li>
          <li className="flex items-start gap-2">
            <ArrowRight className="w-4 h-4 mt-0.5 flex-shrink-0" />
            Báo cáo KQKD theo mẫu B02-DN
          </li>
          <li className="flex items-start gap-2">
            <ArrowRight className="w-4 h-4 mt-0.5 flex-shrink-0" />
            Dự báo dòng tiền bằng AI (Machine Learning)
          </li>
          <li className="flex items-start gap-2">
            <ArrowRight className="w-4 h-4 mt-0.5 flex-shrink-0" />
            Xuất báo cáo theo định dạng XML cho cơ quan thuế
          </li>
        </ul>
      </div>
    </div>
  );
}
