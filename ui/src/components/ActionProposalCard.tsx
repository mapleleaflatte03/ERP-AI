/**
 * ActionProposalCard - UI component for Agent action proposals
 * 
 * Renders when Copilot proposes an action (approve/reject) that requires
 * user confirmation before execution.
 */

import { useState } from 'react';
import { CheckCircle, XCircle, RefreshCw, AlertTriangle, Clock, Check, X } from 'lucide-react';
import api from '../lib/api';

interface ActionProposal {
  action_id: string;
  action_type: 'approve_proposal' | 'reject_proposal' | string;
  description: string;
  status: 'proposed' | 'executed' | 'cancelled' | 'failed';
  requires_confirmation: boolean;
}

interface ActionProposalCardProps {
  proposal: ActionProposal;
  onStatusChange?: (newStatus: string, result?: any) => void;
}

export default function ActionProposalCard({ proposal, onStatusChange }: ActionProposalCardProps) {
  const [status, setStatus] = useState(proposal.status);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);

  const isApprove = proposal.action_type === 'approve_proposal';
  const actionLabel = isApprove ? 'Duyệt chứng từ' : 'Từ chối chứng từ';
  const actionIcon = isApprove ? CheckCircle : XCircle;
  const ActionIcon = actionIcon;

  const handleConfirm = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.confirmAgentAction(proposal.action_id);
      setStatus('executed');
      setResult(response.result);
      onStatusChange?.('executed', response.result);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Không thể thực hiện hành động');
      setStatus('failed');
      onStatusChange?.('failed');
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = async () => {
    setLoading(true);
    setError(null);
    try {
      await api.cancelAgentAction(proposal.action_id);
      setStatus('cancelled');
      onStatusChange?.('cancelled');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Không thể hủy hành động');
    } finally {
      setLoading(false);
    }
  };

  // Already completed states
  if (loading) {
    return (
      <div className="mt-3 p-4 rounded-xl border border-blue-200 bg-blue-50 animate-pulse" aria-busy="true">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-blue-200" />
          <div className="flex-1 space-y-2">
            <div className="h-3 bg-blue-200 rounded w-1/3" />
            <div className="h-4 bg-blue-200 rounded w-2/3" />
            <div className="h-3 bg-blue-200 rounded w-1/2" />
          </div>
        </div>
        <p className="text-xs text-blue-700 mt-3">Đang thực hiện hành động...</p>
      </div>
    );
  }

  if (status === 'executed') {
    return (
      <div className="mt-3 p-4 bg-green-50 border border-green-200 rounded-xl">
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center flex-shrink-0">
            <Check className="w-4 h-4 text-green-600" />
          </div>
          <div className="flex-1">
            <p className="font-medium text-green-800">✅ {actionLabel} - Đã thực hiện</p>
            <p className="text-sm text-green-700 mt-1">{proposal.description}</p>
            {result && (
              <p className="text-xs text-green-600 mt-2">
                {result.message || 'Hành động đã được thực hiện thành công'}
              </p>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (status === 'cancelled') {
    return (
      <div className="mt-3 p-4 bg-gray-50 border border-gray-200 rounded-xl">
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center flex-shrink-0">
            <X className="w-4 h-4 text-gray-500" />
          </div>
          <div className="flex-1">
            <p className="font-medium text-gray-600">❌ {actionLabel} - Đã hủy</p>
            <p className="text-sm text-gray-500 mt-1">{proposal.description}</p>
          </div>
        </div>
      </div>
    );
  }

  if (status === 'failed') {
    return (
      <div className="mt-3 p-4 bg-red-50 border border-red-200 rounded-xl">
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
            <AlertTriangle className="w-4 h-4 text-red-600" />
          </div>
          <div className="flex-1">
            <p className="font-medium text-red-800">⚠️ {actionLabel} - Thất bại</p>
            <p className="text-sm text-red-700 mt-1">{proposal.description}</p>
            {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
          </div>
        </div>
      </div>
    );
  }

  // Pending/proposed state - show buttons
  return (
    <div className={`mt-3 p-4 rounded-xl border-2 ${
      isApprove 
        ? 'bg-blue-50 border-blue-200' 
        : 'bg-orange-50 border-orange-200'
    }`}>
      <div className="flex items-start gap-3">
        <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
          isApprove ? 'bg-blue-100' : 'bg-orange-100'
        }`}>
          <ActionIcon className={`w-5 h-5 ${isApprove ? 'text-blue-600' : 'text-orange-600'}`} />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <Clock className="w-4 h-4 text-gray-400" />
            <span className="text-xs text-gray-500 uppercase tracking-wider">Đề xuất hành động</span>
          </div>
          <p className={`font-semibold ${isApprove ? 'text-blue-900' : 'text-orange-900'}`}>
            {actionLabel}
          </p>
          <p className={`text-sm mt-1 ${isApprove ? 'text-blue-700' : 'text-orange-700'}`}>
            {proposal.description}
          </p>
          
          {error && (
            <p className="text-xs text-red-600 mt-2 flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" />
              {error}
            </p>
          )}
          
          <div className="flex items-center gap-2 mt-4">
            <button
              onClick={handleConfirm}
              disabled={loading}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-white transition-colors disabled:opacity-50 ${
                isApprove 
                  ? 'bg-blue-600 hover:bg-blue-700' 
                  : 'bg-orange-600 hover:bg-orange-700'
              }`}
            >
              {loading ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Check className="w-4 h-4" />
              )}
              Xác nhận
            </button>
            <button
              onClick={handleCancel}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-gray-600 bg-white border border-gray-300 hover:bg-gray-50 transition-colors disabled:opacity-50"
            >
              <X className="w-4 h-4" />
              Hủy bỏ
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
