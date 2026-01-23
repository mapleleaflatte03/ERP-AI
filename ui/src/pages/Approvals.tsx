import { useState, useEffect } from 'react';
import { RefreshCw, Check, X, Loader2, ClipboardCheck, AlertTriangle } from 'lucide-react';
import api from '../lib/api';
import type { Approval } from '../types';

export default function Approvals() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [denyReason, setDenyReason] = useState('');
  const [showDenyModal, setShowDenyModal] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

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

  useEffect(() => {
    fetchApprovals();
  }, []);

  const handleApprove = async (approvalId: string) => {
    setActionLoading(approvalId);
    try {
      await api.approveProposal(approvalId);
      setMessage({ type: 'success', text: 'Proposal approved successfully!' });
      fetchApprovals();
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to approve proposal' });
      console.error(err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeny = async (approvalId: string) => {
    setActionLoading(approvalId);
    try {
      await api.denyProposal(approvalId, 'ui-user', denyReason);
      setMessage({ type: 'success', text: 'Proposal denied' });
      setShowDenyModal(null);
      setDenyReason('');
      fetchApprovals();
    } catch (err) {
      setMessage({ type: 'error', text: 'Failed to deny proposal' });
      console.error(err);
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Message Toast */}
      {message && (
        <div
          className={`p-4 rounded-lg flex items-center justify-between ${
            message.type === 'success' ? 'bg-green-50 border border-green-200 text-green-800' : 'bg-red-50 border border-red-200 text-red-800'
          }`}
        >
          <span>{message.text}</span>
          <button onClick={() => setMessage(null)} className="p-1 hover:bg-white/50 rounded">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Header */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center">
              <ClipboardCheck className="w-5 h-5 text-orange-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Pending Approvals</h2>
              <p className="text-sm text-gray-500">{approvals.length} items waiting for review</p>
            </div>
          </div>
          <button
            onClick={fetchApprovals}
            disabled={loading}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition"
          >
            <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Approvals List */}
      <div className="space-y-4">
        {loading ? (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
            <Loader2 className="w-8 h-8 text-gray-400 animate-spin mx-auto" />
          </div>
        ) : approvals.length === 0 ? (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
            <Check className="w-12 h-12 text-green-500 mx-auto mb-3" />
            <h3 className="text-lg font-medium text-gray-900">All caught up!</h3>
            <p className="text-gray-500">No pending approvals at the moment</p>
          </div>
        ) : (
          approvals.map((approval) => (
            <div
              key={approval.id}
              className="bg-white rounded-xl shadow-sm border border-gray-200 p-6"
            >
              <div className="flex items-start justify-between">
                <div className="space-y-3">
                  <div>
                    <span className="px-2 py-1 bg-orange-100 text-orange-700 text-xs font-medium rounded-full">
                      Pending Approval
                    </span>
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-500">Approval ID:</span>
                      <code className="text-sm font-mono bg-gray-100 px-2 py-0.5 rounded">{approval.id}</code>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-500">Job ID:</span>
                      <code className="text-sm font-mono bg-gray-100 px-2 py-0.5 rounded">{approval.job_id}</code>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-500">Proposal ID:</span>
                      <code className="text-sm font-mono bg-gray-100 px-2 py-0.5 rounded">{approval.proposal_id}</code>
                    </div>
                    <div className="text-xs text-gray-400">
                      Requested: {new Date(approval.requested_at).toLocaleString()}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setShowDenyModal(approval.id)}
                    disabled={actionLoading === approval.id}
                    className="px-4 py-2 border border-red-300 text-red-600 rounded-lg hover:bg-red-50 transition flex items-center gap-2 disabled:opacity-50"
                  >
                    <X className="w-4 h-4" />
                    Deny
                  </button>
                  <button
                    onClick={() => handleApprove(approval.id)}
                    disabled={actionLoading === approval.id}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition flex items-center gap-2 disabled:opacity-50"
                  >
                    {actionLoading === approval.id ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Check className="w-4 h-4" />
                    )}
                    Approve
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Deny Modal */}
      {showDenyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-900/50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-md p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center">
                <AlertTriangle className="w-5 h-5 text-red-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900">Deny Proposal</h3>
            </div>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Reason (optional)
              </label>
              <textarea
                value={denyReason}
                onChange={(e) => setDenyReason(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500 outline-none"
                rows={3}
                placeholder="Enter reason for denial..."
              />
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => {
                  setShowDenyModal(null);
                  setDenyReason('');
                }}
                className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDeny(showDenyModal)}
                disabled={actionLoading === showDenyModal}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {actionLoading === showDenyModal ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  'Confirm Deny'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
