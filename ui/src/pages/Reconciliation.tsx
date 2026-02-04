import { useState } from 'react';
import {
  Link2,
  Unlink,
  AlertTriangle,
  Search,
  ArrowRight,
  Ban,
  HelpCircle,
} from 'lucide-react';
import ModuleChatDock from '../components/moduleChat/ModuleChatDock';

// No mock data - feature not yet implemented in backend


export default function Reconciliation() {
  const [activeTab, setActiveTab] = useState<'unmatched' | 'matched' | 'suspicious'>('unmatched');
  const [selectedTransaction, setSelectedTransaction] = useState<string | null>(null);
  const [selectedInvoice, setSelectedInvoice] = useState<string | null>(null);

  // No data - feature not yet implemented
  
  
  const filteredTransactions: never[] = [];
  const invoices: never[] = [];

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
          { value: 'unmatched', label: 'Chưa khớp', icon: Unlink, count: 0 },
          { value: 'matched', label: 'Đã khớp', icon: Link2, count: 0 },
          { value: 'suspicious', label: 'Nghi vấn', icon: AlertTriangle, count: 0 },
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
                <Unlink className="w-10 h-10 mx-auto text-gray-300 mb-3" />
                <p>Chưa có giao dịch ngân hàng</p>
                <p className="text-sm text-gray-400 mt-1">Tính năng đang phát triển</p>
              </div>
            ) : (
              null
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
            {invoices.length === 0 ? (
              <div className="p-8 text-center text-gray-500">
                <Unlink className="w-10 h-10 mx-auto text-gray-300 mb-3" />
                <p>Chưa có hóa đơn</p>
                <p className="text-sm text-gray-400 mt-1">Tính năng đang phát triển</p>
              </div>
            ) : null}
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

      {/* Module Chat Dock for Reconciliation Agent */}
      <ModuleChatDock 
        module="reconciliation" 
        scope={{ 
          context: 'bank_statement_matching',
          capabilities: 'discrepancy_detection, auto_match, variance_analysis'
        }} 
      />
    </div>
  );
}
