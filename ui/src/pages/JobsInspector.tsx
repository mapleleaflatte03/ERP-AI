import { useState, useEffect } from 'react';
import { 
  Briefcase, RefreshCw, Search, ChevronRight, FileText,
  Clock, CheckCircle, XCircle, AlertTriangle, Loader2,
  Eye, Shield, Map, Activity, Database
} from 'lucide-react';
import api from '../lib/api';
import type { Job } from '../types';

type TabId = 'status' | 'proposal' | 'policy' | 'evidence' | 'timeline' | 'zones' | 'state';

interface TabData {
  proposal?: Record<string, unknown>;
  policy?: Record<string, unknown>;
  evidence?: Record<string, unknown>;
  timeline?: Array<Record<string, unknown>>;
  zones?: Record<string, unknown>;
  state?: Record<string, unknown>;
}

const TABS: { id: TabId; name: string; icon: React.ElementType }[] = [
  { id: 'status', name: 'Status', icon: Eye },
  { id: 'proposal', name: 'Proposal JSON', icon: FileText },
  { id: 'policy', name: 'Policy Result', icon: Shield },
  { id: 'evidence', name: 'Evidence', icon: Database },
  { id: 'timeline', name: 'Timeline', icon: Activity },
  { id: 'zones', name: 'Zones', icon: Map },
  { id: 'state', name: 'State', icon: Briefcase },
];

export default function JobsInspector() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>('status');
  const [tabData, setTabData] = useState<TabData>({});
  const [loading, setLoading] = useState(true);
  const [tabLoading, setTabLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    fetchJobs();
    
    // Check URL for job ID
    const params = new URLSearchParams(window.location.search);
    const jobId = params.get('id');
    if (jobId) {
      loadJobById(jobId);
    }
  }, []);

  const fetchJobs = async () => {
    try {
      const data = await api.listJobs();
      setJobs(data.jobs || []);
    } catch (err) {
      console.error('Failed to fetch jobs:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadJobById = async (jobId: string) => {
    try {
      const job = await api.getJobStatus(jobId);
      setSelectedJob(job);
      setTabData({});
    } catch (err) {
      console.error('Failed to load job:', err);
    }
  };

  const selectJob = (job: Job) => {
    setSelectedJob(job);
    setTabData({});
    setActiveTab('status');
    // Update URL
    window.history.pushState({}, '', `?id=${job.job_id}`);
  };

  const loadTabData = async (tab: TabId) => {
    if (!selectedJob || tab === 'status') return;
    if (tabData[tab]) return; // Already loaded
    
    setTabLoading(true);
    try {
      let data;
      switch (tab) {
        case 'proposal':
          // Get from job result
          data = selectedJob.result || selectedJob.proposal;
          break;
        case 'policy':
          data = await api.getJobPolicy(selectedJob.job_id);
          break;
        case 'evidence':
          data = await api.getJobEvidence(selectedJob.job_id);
          break;
        case 'timeline':
          data = await api.getJobTimeline(selectedJob.job_id);
          break;
        case 'zones':
          data = await api.getJobZones(selectedJob.job_id);
          break;
        case 'state':
          data = await api.getJobState(selectedJob.job_id);
          break;
      }
      setTabData(prev => ({ ...prev, [tab]: data }));
    } catch (err) {
      console.error(`Failed to load ${tab}:`, err);
      setTabData(prev => ({ ...prev, [tab]: { error: String(err) } }));
    } finally {
      setTabLoading(false);
    }
  };

  useEffect(() => {
    if (selectedJob && activeTab !== 'status') {
      loadTabData(activeTab);
    }
  }, [activeTab, selectedJob]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'waiting_for_approval':
        return <AlertTriangle className="w-4 h-4 text-yellow-500" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />;
      case 'queued':
      case 'processing':
        return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
      default:
        return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-700';
      case 'waiting_for_approval': return 'bg-yellow-100 text-yellow-700';
      case 'failed': return 'bg-red-100 text-red-700';
      case 'queued':
      case 'processing': return 'bg-blue-100 text-blue-700';
      default: return 'bg-gray-100 text-gray-700';
    }
  };

  const filteredJobs = jobs.filter(job => 
    job.job_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
    job.filename?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-emerald-600 to-teal-600 rounded-xl shadow-lg p-6 text-white">
        <div className="flex items-center gap-3">
          <Briefcase className="w-8 h-8" />
          <div>
            <h2 className="text-xl font-bold">Jobs Inspector</h2>
            <p className="text-emerald-100 text-sm">Detailed view of all processing jobs</p>
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Jobs List */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="p-4 border-b border-gray-200">
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search jobs..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>
              <button
                onClick={fetchJobs}
                className="p-2 hover:bg-gray-100 rounded-lg"
              >
                <RefreshCw className="w-4 h-4 text-gray-500" />
              </button>
            </div>
          </div>

          <div className="max-h-[600px] overflow-auto">
            {loading ? (
              <div className="p-8 text-center text-gray-500">Loading jobs...</div>
            ) : filteredJobs.length === 0 ? (
              <div className="p-8 text-center text-gray-500">
                <Briefcase className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>No jobs found</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {filteredJobs.map(job => (
                  <div
                    key={job.job_id}
                    onClick={() => selectJob(job)}
                    className={`p-4 cursor-pointer transition ${
                      selectedJob?.job_id === job.job_id
                        ? 'bg-emerald-50 border-l-2 border-emerald-500'
                        : 'hover:bg-gray-50'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      {getStatusIcon(job.status)}
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-gray-900 truncate text-sm">
                          {job.filename || job.job_id}
                        </p>
                        <p className="text-xs text-gray-500 font-mono truncate">
                          {job.job_id.slice(0, 8)}...
                        </p>
                      </div>
                      <ChevronRight className="w-4 h-4 text-gray-400" />
                    </div>
                    <div className="mt-2 flex items-center justify-between">
                      <span className={`text-xs px-2 py-0.5 rounded ${getStatusColor(job.status)}`}>
                        {job.status}
                      </span>
                      <span className="text-xs text-gray-400">
                        {job.created_at ? new Date(job.created_at).toLocaleDateString() : ''}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Job Details */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          {selectedJob ? (
            <>
              {/* Tabs */}
              <div className="flex border-b border-gray-200 overflow-x-auto">
                {TABS.map(tab => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`flex items-center gap-2 px-4 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition ${
                      activeTab === tab.id
                        ? 'border-emerald-500 text-emerald-600'
                        : 'border-transparent text-gray-500 hover:text-gray-700'
                    }`}
                  >
                    <tab.icon className="w-4 h-4" />
                    {tab.name}
                  </button>
                ))}
              </div>

              {/* Tab Content */}
              <div className="p-6">
                {tabLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
                  </div>
                ) : activeTab === 'status' ? (
                  <JobStatusTab job={selectedJob} />
                ) : (
                  <div className="space-y-4">
                    <h4 className="font-medium text-gray-900 capitalize">{activeTab} Data</h4>
                    <pre className="p-4 bg-gray-50 rounded-lg overflow-auto max-h-[500px] text-xs font-mono">
                      {JSON.stringify(tabData[activeTab] || { message: 'No data available' }, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-full min-h-[400px] text-gray-500">
              <div className="text-center">
                <Briefcase className="w-16 h-16 mx-auto mb-4 opacity-50" />
                <p>Select a job to view details</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function JobStatusTab({ job }: { job: Job }) {
  return (
    <div className="space-y-6">
      {/* Status Header */}
      <div className={`p-4 rounded-lg ${
        job.status === 'completed' ? 'bg-green-50 border border-green-200' :
        job.status === 'waiting_for_approval' ? 'bg-yellow-50 border border-yellow-200' :
        job.status === 'failed' ? 'bg-red-50 border border-red-200' :
        'bg-blue-50 border border-blue-200'
      }`}>
        <div className="flex items-center gap-3">
          {job.status === 'completed' && <CheckCircle className="w-6 h-6 text-green-500" />}
          {job.status === 'waiting_for_approval' && <AlertTriangle className="w-6 h-6 text-yellow-500" />}
          {job.status === 'failed' && <XCircle className="w-6 h-6 text-red-500" />}
          {['queued', 'processing'].includes(job.status) && <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />}
          <div>
            <p className="font-medium text-gray-900 capitalize">{job.status.replace('_', ' ')}</p>
            <p className="text-sm text-gray-600">
              {job.status === 'completed' && 'Job processed successfully'}
              {job.status === 'waiting_for_approval' && 'Pending human review'}
              {job.status === 'failed' && (job.error || 'Processing failed')}
            </p>
          </div>
        </div>
      </div>

      {/* Job Info */}
      <div className="grid md:grid-cols-2 gap-4">
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-500">Job Information</h4>
          <dl className="space-y-2">
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Job ID</dt>
              <dd className="text-sm font-mono">{job.job_id}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Filename</dt>
              <dd className="text-sm">{job.filename || '-'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Document Type</dt>
              <dd className="text-sm">{job.document_type || '-'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Tenant</dt>
              <dd className="text-sm">{job.tenant_id || 'default'}</dd>
            </div>
          </dl>
        </div>
        
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-500">Timestamps</h4>
          <dl className="space-y-2">
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Created</dt>
              <dd className="text-sm">{job.created_at ? new Date(job.created_at).toLocaleString() : '-'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Updated</dt>
              <dd className="text-sm">{job.updated_at ? new Date(job.updated_at).toLocaleString() : '-'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">Completed</dt>
              <dd className="text-sm">{job.completed_at ? new Date(job.completed_at).toLocaleString() : '-'}</dd>
            </div>
          </dl>
        </div>
      </div>

      {/* Quick Actions */}
      {job.status === 'waiting_for_approval' && (
        <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
          <p className="text-sm text-yellow-800 mb-3">
            This job requires approval. Go to Approvals Inbox to review.
          </p>
          <a
            href="/approvals"
            className="inline-block px-4 py-2 bg-yellow-500 hover:bg-yellow-600 text-white rounded-lg text-sm"
          >
            Go to Approvals
          </a>
        </div>
      )}
    </div>
  );
}
