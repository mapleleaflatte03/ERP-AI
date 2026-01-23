import { useState } from 'react';
import {
  Link2,
  Unlink,
  AlertTriangle,
  CheckCircle,
  Search,
  ArrowRight,
  Ban,
  HelpCircle,
} from 'lucide-react';

// Mock data for demo
const MOCK_BANK_TRANSACTIONS = [
  { id: 'bt-1', date: '2026-01-20', description: 'TT cho NCC ABC Corp', amount: 15000000, type: 'debit', status: 'unmatched' },
  { id: 'bt-2', date: '2026-01-19', description: 'Thu tiền KH XYZ Ltd', amount: 8500000, type: 'credit', status: 'matched', matched_invoice: 'INV-001' },
  { id: 'bt-3', date: '2026-01-18', description: 'Chi phí vận chuyển', amount: 2300000, type: 'debit', status: 'suspicious' },
  { id: 'bt-4', date: '2026-01-17', description: 'TT hóa đơn #HD456', amount: 45000000, type: 'debit', status: 'unmatched' },
  { id: 'bt-5', date: '2026-01-15', description: 'Thu nợ KH Minh Anh', amount: 12000000, type: 'credit', status: 'matched', matched_invoice: 'INV-002' },
];

const MOCK_INVOICES = [
  { id: 'inv-1', invoice_no: 'HD-2026-001', vendor: 'ABC Corp', amount: 15000000, date: '2026-01-15', status: 'unmatched' },
  { id: 'inv-2', invoice_no: 'HD-2026-002', vendor: 'DEF Ltd', amount: 8500000, date: '2026-01-14', status: 'matched' },
  { id: 'inv-3', invoice_no: 'HD-2026-003', vendor: 'GHI JSC', amount: 45000000, date: '2026-01-10', status: 'unmatched' },
];

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount);
}

export default function Reconciliation() {
  const [activeTab, setActiveTab] = useState<'unmatched' | 'matched' | 'suspicious'>('unmatched');
  const [selectedTransaction, setSelectedTransaction] = useState<string | null>(null);
  const [selectedInvoice, setSelectedInvoice] = useState<string | null>(null);

  const filteredTransactions = MOCK_BANK_TRANSACTIONS.filter(t => t.status === activeTab);

  const handleMatch = () => {
    if (selectedTransaction && selectedInvoice) {
      alert(`Đã khớp giao dịch ${selectedTransaction} với hóa đơn ${selectedInvoice}`);
      setSelectedTransaction(null);
      setSelectedInvoice(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Đối chiếu</h1>
          <p className="text-gray-500 text-sm mt-1">Đối chiếu giao dịch ngân hàng với hóa đơn</p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 bg-yellow-50 border border-yellow-200 rounded-lg">
          <HelpCircle className="w-4 h-4 text-yellow-600" />
          <span className="text-sm text-yellow-700">Tính năng đang phát triển</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        {[
          { value: 'unmatched', label: 'Chưa khớp', icon: Unlink, count: 3 },
          { value: 'matched', label: 'Đã khớp', icon: Link2, count: 2 },
          { value: 'suspicious', label: 'Nghi vấn', icon: AlertTriangle, count: 1 },
        ].map(tab => (
          <button
            key={tab.value}
            onClick={() => setActiveTab(tab.value as typeof activeTab)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeTab === tab.value
                ? 'bg-blue-600 text-white'
                : 'bg-white border hover:bg-gray-50'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
            <span className={`px-1.5 py-0.5 rounded text-xs ${
              activeTab === tab.value ? 'bg-blue-500' : 'bg-gray-100'
            }`}>
              {tab.count}
            </span>
          </button>
        ))}
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Bank Transactions */}
        <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b bg-gray-50">
            <h2 className="font-semibold text-gray-900">Giao dịch ngân hàng</h2>
          </div>
          <div className="divide-y max-h-[500px] overflow-auto">
            {filteredTransactions.length === 0 ? (
              <div className="p-8 text-center text-gray-500">
                <CheckCircle className="w-10 h-10 mx-auto text-green-400 mb-3" />
                <p>Không có giao dịch {activeTab === 'unmatched' ? 'chưa khớp' : activeTab === 'suspicious' ? 'nghi vấn' : ''}</p>
              </div>
            ) : (
              filteredTransactions.map(tx => (
                <div
                  key={tx.id}
                  onClick={() => setSelectedTransaction(tx.id)}
                  className={`p-4 cursor-pointer hover:bg-gray-50 ${
                    selectedTransaction === tx.id ? 'bg-blue-50 border-l-4 border-blue-500' : ''
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-gray-900">{tx.description}</p>
                      <p className="text-sm text-gray-500">{tx.date}</p>
                    </div>
                    <div className="text-right">
                      <p className={`font-medium ${tx.type === 'credit' ? 'text-green-600' : 'text-red-600'}`}>
                        {tx.type === 'credit' ? '+' : '-'}{formatCurrency(tx.amount)}
                      </p>
                      {tx.status === 'suspicious' && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-orange-100 text-orange-700 rounded text-xs">
                          <AlertTriangle className="w-3 h-3" />
                          Nghi vấn
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Invoices */}
        <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b bg-gray-50">
            <h2 className="font-semibold text-gray-900">Hóa đơn</h2>
          </div>
          <div className="p-4 border-b">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Tìm hóa đơn..."
                className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          <div className="divide-y max-h-[400px] overflow-auto">
            {MOCK_INVOICES.filter(inv => inv.status === 'unmatched').map(inv => (
              <div
                key={inv.id}
                onClick={() => setSelectedInvoice(inv.id)}
                className={`p-4 cursor-pointer hover:bg-gray-50 ${
                  selectedInvoice === inv.id ? 'bg-green-50 border-l-4 border-green-500' : ''
                }`}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-gray-900">{inv.invoice_no}</p>
                    <p className="text-sm text-gray-500">{inv.vendor}</p>
                    <p className="text-xs text-gray-400">{inv.date}</p>
                  </div>
                  <p className="font-medium text-gray-900">{formatCurrency(inv.amount)}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Match Action */}
      {selectedTransaction && selectedInvoice && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-white rounded-xl shadow-lg border p-4 flex items-center gap-4">
          <div className="text-sm text-gray-600">
            Khớp giao dịch với hóa đơn?
          </div>
          <button
            onClick={handleMatch}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
          >
            <Link2 className="w-4 h-4" />
            Xác nhận khớp
          </button>
          <button
            onClick={() => {
              setSelectedTransaction(null);
              setSelectedInvoice(null);
            }}
            className="p-2 hover:bg-gray-100 rounded-lg"
          >
            <Ban className="w-4 h-4 text-gray-500" />
          </button>
        </div>
      )}

      {/* Coming Soon Notice */}
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-xl p-6">
        <h3 className="font-semibold text-blue-900">Tính năng đối chiếu tự động (Coming soon)</h3>
        <ul className="mt-3 text-sm text-blue-700 space-y-2">
          <li className="flex items-start gap-2">
            <ArrowRight className="w-4 h-4 mt-0.5 flex-shrink-0" />
            Tự động import giao dịch từ sao kê ngân hàng (PDF/XLSX)
          </li>
          <li className="flex items-start gap-2">
            <ArrowRight className="w-4 h-4 mt-0.5 flex-shrink-0" />
            AI matching: Tự động gợi ý khớp dựa trên số tiền, mô tả, mã tham chiếu
          </li>
          <li className="flex items-start gap-2">
            <ArrowRight className="w-4 h-4 mt-0.5 flex-shrink-0" />
            Phát hiện bất thường: Giao dịch không có hóa đơn tương ứng
          </li>
        </ul>
      </div>
    </div>
  );
}
