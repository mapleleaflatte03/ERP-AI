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

// Mock data for general ledger
const MOCK_LEDGER_DATA = [
  { account: '111', name: 'Tiền mặt', opening: 50000000, debit: 120000000, credit: 95000000, closing: 75000000 },
  { account: '112', name: 'Tiền gửi ngân hàng', opening: 200000000, debit: 350000000, credit: 280000000, closing: 270000000 },
  { account: '131', name: 'Phải thu KH', opening: 80000000, debit: 150000000, credit: 120000000, closing: 110000000 },
  { account: '152', name: 'Nguyên vật liệu', opening: 45000000, debit: 60000000, credit: 55000000, closing: 50000000 },
  { account: '331', name: 'Phải trả NCC', opening: 65000000, debit: 70000000, credit: 90000000, closing: 85000000 },
  { account: '511', name: 'Doanh thu', opening: 0, debit: 0, credit: 280000000, closing: 280000000 },
  { account: '632', name: 'Giá vốn hàng bán', opening: 0, debit: 180000000, credit: 0, closing: 180000000 },
  { account: '642', name: 'Chi phí quản lý', opening: 0, debit: 35000000, credit: 0, closing: 35000000 },
];

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('vi-VN').format(amount);
}

export default function Reports() {
  const [selectedReport, setSelectedReport] = useState<string | null>('general_ledger');
  const [dateRange, setDateRange] = useState({ from: '2026-01-01', to: '2026-01-23' });
  const [isGenerating, setIsGenerating] = useState(false);

  const handleGenerate = () => {
    setIsGenerating(true);
    setTimeout(() => setIsGenerating(false), 1500);
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
            className={`relative text-left p-4 rounded-xl border transition-all ${
              selectedReport === report.id
                ? 'bg-blue-50 border-blue-300 ring-2 ring-blue-500'
                : report.available
                  ? 'bg-white hover:bg-gray-50 hover:border-gray-300'
                  : 'bg-gray-50 opacity-60 cursor-not-allowed'
            }`}
          >
            {!report.available && (
              <div className="absolute top-2 right-2">
                <Lock className="w-4 h-4 text-gray-400" />
              </div>
            )}
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center mb-3 ${
              selectedReport === report.id ? 'bg-blue-100' : 'bg-gray-100'
            }`}>
              <report.icon className={`w-5 h-5 ${
                selectedReport === report.id ? 'text-blue-600' : 'text-gray-500'
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
              disabled={isGenerating}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {isGenerating ? (
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
            <table className="w-full">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mã TK</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tên tài khoản</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Số dư đầu kỳ</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Phát sinh Nợ</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Phát sinh Có</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Số dư cuối kỳ</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {MOCK_LEDGER_DATA.map(row => (
                  <tr key={row.account} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-sm font-medium text-gray-900">{row.account}</td>
                    <td className="px-4 py-3 text-sm text-gray-700">{row.name}</td>
                    <td className="px-4 py-3 text-sm text-right text-gray-600">{formatCurrency(row.opening)}</td>
                    <td className="px-4 py-3 text-sm text-right text-blue-600">{formatCurrency(row.debit)}</td>
                    <td className="px-4 py-3 text-sm text-right text-red-600">{formatCurrency(row.credit)}</td>
                    <td className="px-4 py-3 text-sm text-right font-medium text-gray-900">{formatCurrency(row.closing)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-gray-50 border-t font-medium">
                <tr>
                  <td colSpan={2} className="px-4 py-3 text-right text-sm text-gray-700">Tổng cộng:</td>
                  <td className="px-4 py-3 text-right text-sm">{formatCurrency(440000000)}</td>
                  <td className="px-4 py-3 text-right text-sm text-blue-600">{formatCurrency(965000000)}</td>
                  <td className="px-4 py-3 text-right text-sm text-red-600">{formatCurrency(920000000)}</td>
                  <td className="px-4 py-3 text-right text-sm">{formatCurrency(485000000)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}

      {selectedReport === 'trial_balance' && (
        <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b bg-gray-50">
            <h2 className="font-semibold text-gray-900">Bảng cân đối phát sinh</h2>
          </div>
          <div className="p-8 text-center text-gray-500">
            <BarChart3 className="w-12 h-12 mx-auto text-gray-300 mb-4" />
            <p>Chọn kỳ báo cáo và nhấn "Tạo báo cáo"</p>
          </div>
        </div>
      )}

      {/* Coming Soon Notice */}
      <div className="bg-gradient-to-r from-purple-50 to-pink-50 border border-purple-200 rounded-xl p-6">
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
