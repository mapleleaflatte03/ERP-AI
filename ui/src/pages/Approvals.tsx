import { useState, useEffect } from 'react';
import { 
  CheckSquare, RefreshCw, Check, X, Loader2, 
  AlertTriangle, FileText, DollarSign, User
} from 'lucide-react';
import api from '../lib/api';
import type { Approval } from '../types';

export default function ApprovalsInbox() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState<Record<string, 'approving' | 'rejecting'>>({});
  const [selectedApproval, setSelectedApproval] = useState<Approval | null>(null);
  const [actionResult, setActionResult] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  useEffect(() => {
    fetchApprovals();
  }, []);

  const fetchApprovals = async () => {
    setLoading(true);
    try {
      const data = await api.listPendingApprovals();
      setApprovals(data.approvals || []);
    } catch (err) {
      console.error('Failed to fetch approvals:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (approval: Approval) => {
    const id = approval.id || approval.job_id;
    setProcessing(prev => ({ ...prev, [id]: 'approving' }));
    setActionResult(null);
    
    try {
      const result = approval.id 
        ? await api.approveProposal(approval.id)
        : await api.approveByJobId(approval.job_id);
      
      setActionResult({
        type: 'success',
        message: `Approved! Ledger entries created: ${result.ledger_entries_created || 'Yes'}, Balanced: ${result.balanced ? 'Yes' : 'Check required'}`
      });
      
      // Remove from list
      setApprovals(prev => prev.filter(a => (a.id || a.job_id) !== id));
      setSelectedApproval(null);
    } catch (err) {
      setActionResult({
        type: 'error',
        message: `Approval failed: ${err}`
      });
    } finally {
      setProcessing(prev => {
        const { [id]: _, ...rest } = prev;
        return rest;
      });
    }
  };

  const handleReject = async (approval: Approval) => {
    const id = approval.id || approval.job_id;
    setProcessing(prev => ({ ...prev, [id]: 'rejecting' }));
    setActionResult(null);
    
    try {
      approval.id 
        ? await api.rejectProposal(approval.id)
        : await api.rejectByJobId(approval.job_id);
      
      setActionResult({
        type: 'success',
        message: 'Proposal rejected successfully'
      });
      
      // Remove from list
      setApprovals(prev => prev.filter(a => (a.id || a.job_id) !== id));
      setSelectedApproval(null);
    } catch (err) {
      setActionResult({
        type: 'error',
        message: `Rejection failed: ${err}`
      });
    } finally {
      setProcessing(prev => {
        const { [id]: _, ...rest } = prev;
        return rest;
      });
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
    }).format(amount);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-amber-500 to-orange-500 rounded-xl shadow-lg p-6 text-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CheckSquare className="w-8 h-8" />
            <div>
              <h2 className="text-xl font-bold">Approvals Inbox</h2>
              <p className="text-amber-100 text-sm">Review and approve pending journal proposals</p>
            </div>
          </div>
          <button
            onClick={fetchApprovals}
            disabled={loading}
            className="px-4 py-2 bg-white/20 hover:bg-white/30 rounded-lg flex items-center gap-2 transition"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
        
        <div className="mt-4 flex items-center gap-2">
          <span className="px-3 py-1 bg-white/20 rounded-full text-sm">
            {approvals.length} pending
          </span>
        </div>
      </div>

      {/* Action Result Toast */}
      {actionResult && (
        <div className={`p-4 rounded-lg flex items-center gap-3 ${
          actionResult.type === 'success' 
            ? 'bg-green-50 border border-green-200 text-green-700'
            : 'bg-red-50 border border-red-200 text-red-700'
        }`}>
          {actionResult.type === 'success' ? (
            <Check className="w-5 h-5" />
          ) : (
            <AlertTriangle className="w-5 h-5" />
          )}
          <span>{actionResult.message}</span>
          <button 
            onClick={() => setActionResult(null)}
            className="ml-auto p-1 hover:bg-black/10 rounded"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Approvals List */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="p-4 border-b border-gray-200">
            <h3 className="font-medium text-gray-900">Pending Approvals</h3>
          </div>
          
          {loading ? (
            <div className="p-8 text-center text-gray-500">
              <Loader2 className="w-8 h-8 animate-spin mx-auto mb-2" />
              Loading approvals...
            </div>
          ) : approvals.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              <CheckSquare className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p>No pending approvals</p>
              <p className="text-sm mt-1">All caught up! 🎉</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100 max-h-[500px] overflow-auto">
              {approvals.map(approval => {
                const id = approval.id || approval.job_id;
                const isProcessing = processing[id];
                
                return (
                  <div
                    key={id}
                    onClick={() => setSelectedApproval(approval)}
                    className={`p-4 cursor-pointer transition ${
                      selectedApproval?.job_id === approval.job_id
                        ? 'bg-amber-50 border-l-2 border-amber-500'
                        : 'hover:bg-gray-50'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div className="p-2 bg-amber-100 rounded-lg">
                        <FileText className="w-5 h-5 text-amber-600" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-gray-900 truncate">
                          {approval.filename || approval.vendor_name || 'Document'}
                        </p>
                        <p className="text-xs text-gray-500 font-mono truncate">
                          Job: {approval.job_id.slice(0, 8)}...
                        </p>
                        {approval.total_amount && (
                          <p className="text-sm font-medium text-gray-700 mt-1">
                            {formatCurrency(approval.total_amount)}
                          </p>
                        )}
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={(e) => { e.stopPropagation(); handleApprove(approval); }}
                          disabled={!!isProcessing}
                          className="p-2 bg-green-100 hover:bg-green-200 text-green-600 rounded-lg transition disabled:opacity-50"
                          title="Approve"
                        >
                          {isProcessing === 'approving' ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Check className="w-4 h-4" />
                          )}
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleReject(approval); }}
                          disabled={!!isProcessing}
                          className="p-2 bg-red-100 hover:bg-red-200 text-red-600 rounded-lg transition disabled:opacity-50"
                          title="Reject"
                        >
                          {isProcessing === 'rejecting' ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <X className="w-4 h-4" />
                          )}
                        </button>
                      </div>
                    </div>
                    <div className="mt-2 text-xs text-gray-400">
                      {approval.created_at ? new Date(approval.created_at).toLocaleString() : ''}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Approval Detail */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          {selectedApproval ? (
            <>
              <div className="p-4 border-b border-gray-200">
                <h3 className="font-medium text-gray-900">Proposal Details</h3>
              </div>
              <div className="p-4 space-y-4 max-h-[500px] overflow-auto">
                {/* Summary */}
                <div className="p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-center gap-3 mb-3">
                    <DollarSign className="w-5 h-5 text-gray-500" />
                    <span className="font-medium text-gray-900">
                      {selectedApproval.total_amount 
                        ? formatCurrency(selectedApproval.total_amount)
                        : 'Amount TBD'}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <User className="w-5 h-5 text-gray-500" />
                    <span className="text-gray-700">
                      {selectedApproval.vendor_name || 'Unknown Vendor'}
                    </span>
                  </div>
                </div>

                {/* Reason */}
                {selectedApproval.reason && (
                  <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                    <p className="text-sm font-medium text-yellow-800 mb-1">Requires Approval Because:</p>
                    <p className="text-sm text-yellow-700">{selectedApproval.reason}</p>
                  </div>
                )}

                {/* Journal Lines */}
                {selectedApproval.proposal?.journal_lines && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-500 mb-2">Journal Lines</h4>
                    <div className="border border-gray-200 rounded-lg overflow-hidden">
                      <table className="w-full text-sm">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-3 py-2 text-left">Account</th>
                            <th className="px-3 py-2 text-right">Debit</th>
                            <th className="px-3 py-2 text-right">Credit</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {selectedApproval.proposal.journal_lines.map((line: any, idx: number) => (
                            <tr key={idx}>
                              <td className="px-3 py-2">{line.account_code || line.account}</td>
                              <td className="px-3 py-2 text-right">
                                {line.debit ? formatCurrency(line.debit) : '-'}
                              </td>
                              <td className="px-3 py-2 text-right">
                                {line.credit ? formatCurrency(line.credit) : '-'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Raw JSON */}
                <details className="text-sm">
                  <summary className="cursor-pointer text-gray-500 hover:text-gray-700">
                    View Raw Proposal JSON
                  </summary>
                  <pre className="mt-2 p-3 bg-gray-50 rounded-lg overflow-auto text-xs">
                    {JSON.stringify(selectedApproval.proposal || selectedApproval, null, 2)}
                  </pre>
                </details>

                {/* Action Buttons */}
                <div className="flex gap-3 pt-4 border-t border-gray-200">
                  <button
                    onClick={() => handleApprove(selectedApproval)}
                    disabled={!!processing[selectedApproval.id || selectedApproval.job_id]}
                    className="flex-1 py-3 bg-green-600 hover:bg-green-700 text-white rounded-lg flex items-center justify-center gap-2 transition disabled:opacity-50"
                  >
                    {processing[selectedApproval.id || selectedApproval.job_id] === 'approving' ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Check className="w-4 h-4" />
                    )}
                    Approve & Post
                  </button>
                  <button
                    onClick={() => handleReject(selectedApproval)}
                    disabled={!!processing[selectedApproval.id || selectedApproval.job_id]}
                    className="flex-1 py-3 bg-red-600 hover:bg-red-700 text-white rounded-lg flex items-center justify-center gap-2 transition disabled:opacity-50"
                  >
                    {processing[selectedApproval.id || selectedApproval.job_id] === 'rejecting' ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <X className="w-4 h-4" />
                    )}
                    Reject
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-full min-h-[400px] text-gray-500">
              <div className="text-center">
                <CheckSquare className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>Select an approval to view details</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
