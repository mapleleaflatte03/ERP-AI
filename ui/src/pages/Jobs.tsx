import { useState, useEffect, useCallback } from 'react';
import { Upload, RefreshCw, Copy, Check, Clock, CheckCircle2, XCircle, AlertCircle, Loader2 } from 'lucide-react';
import api from '../lib/api';
import type { Job } from '../types';

const statusColors: Record<string, string> = {
  queued: 'bg-gray-100 text-gray-700',
  extracting: 'bg-blue-100 text-blue-700',
  extracted: 'bg-blue-100 text-blue-700',
  llm_proposed: 'bg-purple-100 text-purple-700',
  policy_evaluated: 'bg-yellow-100 text-yellow-700',
  needs_approval: 'bg-orange-100 text-orange-700',
  auto_approved: 'bg-green-100 text-green-700',
  approved: 'bg-green-100 text-green-700',
  posting_to_ledger: 'bg-indigo-100 text-indigo-700',
  posted_to_ledger: 'bg-indigo-100 text-indigo-700',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
};

const statusIcons: Record<string, React.ReactNode> = {
  queued: <Clock className="w-4 h-4" />,
  completed: <CheckCircle2 className="w-4 h-4" />,
  failed: <XCircle className="w-4 h-4" />,
  needs_approval: <AlertCircle className="w-4 h-4" />,
};

export default function Jobs() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [polling, setPolling] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  const fetchJobs = useCallback(async () => {
    try {
      const data = await api.listJobs();
      setJobs(data.jobs || []);
    } catch (err) {
      console.error('Failed to fetch jobs:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  // Auto-poll selected job
  useEffect(() => {
    if (!selectedJob || ['completed', 'failed'].includes(selectedJob.status)) {
      return;
    }

    setPolling(true);
    const interval = setInterval(async () => {
      try {
        const data = await api.getJobStatus(selectedJob.job_id);
        setSelectedJob(data);
        if (['completed', 'failed'].includes(data.status)) {
          setPolling(false);
          fetchJobs();
        }
      } catch (err) {
        console.error('Poll failed:', err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [selectedJob, fetchJobs]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      const data = await api.uploadDocument(file);
      setSelectedJob({ job_id: data.job_id, status: 'queued', tenant_id: 'default', created_at: new Date().toISOString(), updated_at: new Date().toISOString() });
      fetchJobs();
    } catch (err) {
      console.error('Upload failed:', err);
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const copyToClipboard = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopied(key);
    setTimeout(() => setCopied(null), 2000);
  };

  return (
    <div className="grid lg:grid-cols-2 gap-6">
      {/* Left: Upload & Job List */}
      <div className="space-y-6">
        {/* Upload Card */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Upload Document</h2>
          <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition">
            <input
              type="file"
              className="hidden"
              accept=".pdf,.png,.jpg,.jpeg,.xlsx"
              onChange={handleUpload}
              disabled={uploading}
            />
            {uploading ? (
              <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
            ) : (
              <>
                <Upload className="w-8 h-8 text-gray-400 mb-2" />
                <span className="text-sm text-gray-500">Click to upload (PDF, PNG, XLSX)</span>
              </>
            )}
          </label>
        </div>

        {/* Job List */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200">
          <div className="flex items-center justify-between p-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Recent Jobs</h2>
            <button
              onClick={fetchJobs}
              disabled={loading}
              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition"
            >
              <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
          <div className="divide-y divide-gray-100 max-h-96 overflow-y-auto">
            {jobs.length === 0 ? (
              <div className="p-8 text-center text-gray-500">No jobs found</div>
            ) : (
              jobs.map((job) => (
                <button
                  key={job.job_id}
                  onClick={() => setSelectedJob(job)}
                  className={`w-full p-4 text-left hover:bg-gray-50 transition ${selectedJob?.job_id === job.job_id ? 'bg-blue-50' : ''}`}
                >
                  <div className="flex items-center justify-between">
                    <code className="text-xs text-gray-500 font-mono">{job.job_id.slice(0, 8)}...</code>
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${statusColors[job.status] || 'bg-gray-100'}`}>
                      {job.status}
                    </span>
                  </div>
                  <div className="text-xs text-gray-400 mt-1">
                    {new Date(job.created_at).toLocaleString()}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Right: Job Detail */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        {selectedJob ? (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Job Details</h2>
              <div className="flex items-center gap-2">
                {polling && <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />}
                <span className={`px-3 py-1.5 text-sm font-medium rounded-full flex items-center gap-1.5 ${statusColors[selectedJob.status] || 'bg-gray-100'}`}>
                  {statusIcons[selectedJob.status]}
                  {selectedJob.status}
                </span>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <div className="text-xs text-gray-500">Job ID</div>
                  <code className="text-sm font-mono">{selectedJob.job_id}</code>
                </div>
                <button
                  onClick={() => copyToClipboard(selectedJob.job_id, 'job_id')}
                  className="p-2 hover:bg-gray-200 rounded transition"
                >
                  {copied === 'job_id' ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4 text-gray-400" />}
                </button>
              </div>

              {selectedJob.document_id && (
                <div className="p-3 bg-gray-50 rounded-lg">
                  <div className="text-xs text-gray-500">Document ID</div>
                  <code className="text-sm font-mono">{selectedJob.document_id}</code>
                </div>
              )}

              {selectedJob.extracted_invoice_id && (
                <div className="p-3 bg-gray-50 rounded-lg">
                  <div className="text-xs text-gray-500">Extracted Invoice ID</div>
                  <code className="text-sm font-mono">{selectedJob.extracted_invoice_id}</code>
                </div>
              )}

              {selectedJob.journal_proposal_id && (
                <div className="p-3 bg-gray-50 rounded-lg">
                  <div className="text-xs text-gray-500">Journal Proposal ID</div>
                  <code className="text-sm font-mono">{selectedJob.journal_proposal_id}</code>
                </div>
              )}

              {selectedJob.approval_id && (
                <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
                  <div className="text-xs text-blue-600">Approval Required</div>
                  <code className="text-sm font-mono text-blue-800">{selectedJob.approval_id}</code>
                </div>
              )}

              {selectedJob.ledger_entry_id && (
                <div className="p-3 bg-green-50 rounded-lg border border-green-200">
                  <div className="text-xs text-green-600">Ledger Entry ID</div>
                  <code className="text-sm font-mono text-green-800">{selectedJob.ledger_entry_id}</code>
                </div>
              )}

              {selectedJob.temporal_workflow_id && (
                <div className="p-3 bg-gray-50 rounded-lg">
                  <div className="text-xs text-gray-500">Temporal Workflow</div>
                  <code className="text-sm font-mono">{selectedJob.temporal_workflow_id}</code>
                </div>
              )}

              {selectedJob.error_message && (
                <div className="p-3 bg-red-50 rounded-lg border border-red-200">
                  <div className="text-xs text-red-600">Error</div>
                  <div className="text-sm text-red-800">{selectedJob.error_message}</div>
                </div>
              )}
            </div>

            {/* cURL Command */}
            <div className="mt-6 p-4 bg-gray-900 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-gray-400">cURL Command</span>
                <button
                  onClick={() => copyToClipboard(`curl -s http://localhost:8080/api/v1/jobs/${selectedJob.job_id}/status -H "Authorization: Bearer $TOKEN"`, 'curl')}
                  className="p-1 hover:bg-gray-700 rounded transition"
                >
                  {copied === 'curl' ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4 text-gray-400" />}
                </button>
              </div>
              <code className="text-xs text-green-400 font-mono break-all">
                curl -s http://localhost:8080/api/v1/jobs/{selectedJob.job_id}/status -H "Authorization: Bearer $TOKEN"
              </code>
            </div>
          </div>
        ) : (
          <div className="h-full flex items-center justify-center text-gray-400">
            <div className="text-center">
              <Upload className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>Upload a document or select a job to view details</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
