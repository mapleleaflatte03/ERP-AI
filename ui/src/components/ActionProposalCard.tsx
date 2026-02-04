/**
 * ActionProposalCard - UI component for Agent action proposals
 * 
 * Renders when Copilot proposes an action (approve/reject) that requires
 * user confirmation before execution.
 * 
 * Features:
 * - Optimistic UI updates (instant feedback)
 * - Quantum shimmer loading states
 * - Graceful error recovery with rollback
 */

import { useState, useCallback, useRef } from 'react';
import { CheckCircle, XCircle, RefreshCw, AlertTriangle, Clock, Check, X, Undo2 } from 'lucide-react';
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

type OptimisticState = {
  status: string;
  isOptimistic: boolean;
  previousStatus: string;
};

export default function ActionProposalCard({ proposal, onStatusChange }: ActionProposalCardProps) {
  const [optimisticState, setOptimisticState] = useState<OptimisticState>({
    status: proposal.status,
    isOptimistic: false,
    previousStatus: proposal.status,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);
  const [canUndo, setCanUndo] = useState(false);
  const undoTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const status = optimisticState.status;
  const isApprove = proposal.action_type === 'approve_proposal';
  const actionLabel = isApprove ? 'Duyệt chứng từ' : 'Từ chối chứng từ';
  const actionIcon = isApprove ? CheckCircle : XCircle;
  const ActionIcon = actionIcon;

  // Optimistic update with rollback capability
  const setOptimisticStatus = useCallback((newStatus: string) => {
    setOptimisticState(prev => ({
      status: newStatus,
      isOptimistic: true,
      previousStatus: prev.status,
    }));
  }, []);

  const rollbackStatus = useCallback(() => {
    setOptimisticState(prev => ({
      status: prev.previousStatus,
      isOptimistic: false,
      previousStatus: prev.previousStatus,
    }));
  }, []);

  const confirmStatus = useCallback((finalStatus: string) => {
    setOptimisticState({
      status: finalStatus,
      isOptimistic: false,
      previousStatus: finalStatus,
    });
  }, []);

  const handleConfirm = async () => {
    // Optimistic update - show success immediately
    setOptimisticStatus('executed');
    setError(null);
    setCanUndo(true);

    // Allow undo for 3 seconds
    if (undoTimeoutRef.current) {
      clearTimeout(undoTimeoutRef.current);
    }

    undoTimeoutRef.current = setTimeout(async () => {
      setCanUndo(false);
      setLoading(true);
      
      try {
        const response = await api.confirmAgentAction(proposal.action_id);
        confirmStatus('executed');
        setResult(response.result);
        onStatusChange?.('executed', response.result);
      } catch (err: any) {
        // Rollback on error
        rollbackStatus();
        setError(err.response?.data?.detail || 'Không thể thực hiện hành động');
        onStatusChange?.('failed');
      } finally {
        setLoading(false);
      }
    }, 3000);
  };

  const handleUndo = () => {
    if (undoTimeoutRef.current) {
      clearTimeout(undoTimeoutRef.current);
    }
    setCanUndo(false);
    rollbackStatus();
  };

  const handleCancel = async () => {
    // Optimistic update
    setOptimisticStatus('cancelled');
    setError(null);
    setLoading(true);

    try {
      await api.cancelAgentAction(proposal.action_id);
      confirmStatus('cancelled');
      onStatusChange?.('cancelled');
    } catch (err: any) {
      rollbackStatus();
      setError(err.response?.data?.detail || 'Không thể hủy hành động');
    } finally {
      setLoading(false);
    }
  };

  // Quantum Shimmer Loading State
  if (loading && !optimisticState.isOptimistic) {
    return (
      <div className="mt-3 p-4 rounded-xl border border-blue-200 bg-blue-50 quantum-shimmer" aria-busy="true">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full shimmer-element" />
          <div className="flex-1 space-y-2">
            <div className="h-3 shimmer-element rounded w-1/3" />
            <div className="h-4 shimmer-element rounded w-2/3" />
            <div className="h-3 shimmer-element rounded w-1/2" />
          </div>
        </div>
        <p className="text-xs text-blue-700 mt-3 flex items-center gap-2">
          <span className="quantum-pulse" />
          Đang thực hiện hành động...
        </p>
      </div>
    );
  }

  // Executed state (with undo option if optimistic)
  if (status === 'executed') {
    return (
      <div className={`mt-3 p-4 border rounded-xl transition-all duration-200 ${
        optimisticState.isOptimistic 
          ? 'bg-green-50/80 border-green-300 border-dashed' 
          : 'bg-green-50 border-green-200'
      }`}>
        <div className="flex items-start gap-3">
          <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
            optimisticState.isOptimistic ? 'bg-green-100 animate-pulse' : 'bg-green-100'
          }`}>
            <Check className="w-4 h-4 text-green-600" />
          </div>
          <div className="flex-1">
            <div className="flex items-center justify-between">
              <p className="font-medium text-green-800">
                {optimisticState.isOptimistic ? '⏳' : '✅'} {actionLabel} - {optimisticState.isOptimistic ? 'Đang xử lý...' : 'Đã thực hiện'}
              </p>
              {canUndo && (
                <button
                  onClick={handleUndo}
                  className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-green-700 bg-green-100 hover:bg-green-200 rounded-lg transition-colors"
                >
                  <Undo2 className="w-3 h-3" />
                  Hoàn tác (3s)
                </button>
              )}
            </div>
            <p className="text-sm text-green-700 mt-1">{proposal.description}</p>
            {result && !optimisticState.isOptimistic && (
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
