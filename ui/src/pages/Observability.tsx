import { useState, useEffect } from 'react';
import { 
  Eye, RefreshCw, Loader2, ExternalLink,
  Database, HardDrive, Brain, GitBranch, Activity,
  BarChart3, FlaskConical, CheckCircle, AlertTriangle
} from 'lucide-react';
import api from '../lib/api';

interface EvidenceData {
  postgres?: {
    invoices?: number;
    approvals?: number;
    ledger_entries?: number;
    outbox_events?: number;
    job_runs?: number;
    forecasts?: number;
    simulations?: number;
    insights?: number;
  };
  minio?: {
    bucket_count?: number;
    object_count?: number;
    buckets?: string[];
  };
  qdrant?: {
    collection_count?: number;
    points_count?: number;
    collections?: string[];
  };
  temporal?: {
    connected?: boolean;
    workflow_count?: number;
  };
  jaeger?: {
    connected?: boolean;
    service_count?: number;
    services?: string[];
  };
  mlflow?: {
    connected?: boolean;
    experiment_count?: number;
    run_count?: number;
  };
}

const EXTERNAL_LINKS = [
  { name: 'Temporal UI', url: 'http://localhost:8088', icon: GitBranch, description: 'Workflow orchestration' },
  { name: 'Jaeger', url: 'http://localhost:16686', icon: Activity, description: 'Distributed tracing' },
  { name: 'Grafana', url: 'http://localhost:3001', icon: BarChart3, description: 'Metrics & dashboards' },
  { name: 'MinIO Console', url: 'http://localhost:9001', icon: HardDrive, description: 'Object storage' },
  { name: 'Qdrant Dashboard', url: 'http://localhost:6333/dashboard', icon: Brain, description: 'Vector database' },
  { name: 'MLflow', url: 'http://localhost:5000', icon: FlaskConical, description: 'ML experiments' },
];

export default function Observability() {
  const [evidence, setEvidence] = useState<EvidenceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchEvidence();
  }, []);

  const fetchEvidence = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getEvidence();
      setEvidence(data);
    } catch (err) {
      setError(`Failed to fetch evidence: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const CountCard = ({ 
    label, 
    value, 
    icon: Icon 
  }: { 
    label: string; 
    value: number | string | undefined; 
    icon: React.ElementType 
  }) => (
    <div className="bg-gray-50 rounded-lg p-4 flex items-center gap-3">
      <div className="p-2 bg-white rounded-lg shadow-sm">
        <Icon className="w-5 h-5 text-gray-600" />
      </div>
      <div>
        <p className="text-2xl font-bold text-gray-900">{value ?? '-'}</p>
        <p className="text-xs text-gray-500">{label}</p>
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-violet-600 to-purple-600 rounded-xl shadow-lg p-6 text-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Eye className="w-8 h-8" />
            <div>
              <h2 className="text-xl font-bold">Evidence & Observability</h2>
              <p className="text-violet-100 text-sm">System-wide metrics and external tool links</p>
            </div>
          </div>
          <button
            onClick={fetchEvidence}
            disabled={loading}
            className="px-4 py-2 bg-white/20 hover:bg-white/30 rounded-lg flex items-center gap-2 transition"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-red-700">
          <AlertTriangle className="w-6 h-6 mb-2" />
          <p>{error}</p>
        </div>
      ) : (
        <>
          {/* Database Counters */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
            <div className="flex items-center gap-2 mb-4">
              <Database className="w-5 h-5 text-blue-500" />
              <h3 className="font-medium text-gray-900">PostgreSQL Counters</h3>
              <CheckCircle className="w-4 h-4 text-green-500 ml-auto" />
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <CountCard label="Job Runs" value={evidence?.postgres?.job_runs} icon={Activity} />
              <CountCard label="Invoices" value={evidence?.postgres?.invoices} icon={Database} />
              <CountCard label="Approvals" value={evidence?.postgres?.approvals} icon={CheckCircle} />
              <CountCard label="Ledger Entries" value={evidence?.postgres?.ledger_entries} icon={Database} />
              <CountCard label="Outbox Events" value={evidence?.postgres?.outbox_events} icon={Activity} />
              <CountCard label="Forecasts" value={evidence?.postgres?.forecasts} icon={BarChart3} />
              <CountCard label="Simulations" value={evidence?.postgres?.simulations} icon={FlaskConical} />
              <CountCard label="CFO Insights" value={evidence?.postgres?.insights} icon={Brain} />
            </div>
          </div>

          {/* Storage & Vector */}
          <div className="grid md:grid-cols-2 gap-6">
            {/* MinIO */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
              <div className="flex items-center gap-2 mb-4">
                <HardDrive className="w-5 h-5 text-orange-500" />
                <h3 className="font-medium text-gray-900">MinIO Object Storage</h3>
                {evidence?.minio?.bucket_count ? (
                  <CheckCircle className="w-4 h-4 text-green-500 ml-auto" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-yellow-500 ml-auto" />
                )}
              </div>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-500">Buckets</span>
                  <span className="font-medium">{evidence?.minio?.bucket_count ?? '-'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Objects</span>
                  <span className="font-medium">{evidence?.minio?.object_count ?? '-'}</span>
                </div>
                {evidence?.minio?.buckets && (
                  <div className="pt-2 border-t border-gray-100">
                    <p className="text-xs text-gray-400 mb-1">Buckets:</p>
                    <div className="flex flex-wrap gap-1">
                      {evidence.minio.buckets.map(b => (
                        <span key={b} className="px-2 py-0.5 bg-gray-100 rounded text-xs">{b}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Qdrant */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
              <div className="flex items-center gap-2 mb-4">
                <Brain className="w-5 h-5 text-purple-500" />
                <h3 className="font-medium text-gray-900">Qdrant Vector DB</h3>
                {evidence?.qdrant?.collection_count ? (
                  <CheckCircle className="w-4 h-4 text-green-500 ml-auto" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-yellow-500 ml-auto" />
                )}
              </div>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-500">Collections</span>
                  <span className="font-medium">{evidence?.qdrant?.collection_count ?? '-'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Total Points</span>
                  <span className="font-medium">{evidence?.qdrant?.points_count ?? '-'}</span>
                </div>
                {evidence?.qdrant?.collections && (
                  <div className="pt-2 border-t border-gray-100">
                    <p className="text-xs text-gray-400 mb-1">Collections:</p>
                    <div className="flex flex-wrap gap-1">
                      {evidence.qdrant.collections.map(c => (
                        <span key={c} className="px-2 py-0.5 bg-gray-100 rounded text-xs">{c}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Workflow & Tracing */}
          <div className="grid md:grid-cols-3 gap-6">
            {/* Temporal */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
              <div className="flex items-center gap-2 mb-4">
                <GitBranch className="w-5 h-5 text-teal-500" />
                <h3 className="font-medium text-gray-900">Temporal</h3>
                {evidence?.temporal?.connected ? (
                  <CheckCircle className="w-4 h-4 text-green-500 ml-auto" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-yellow-500 ml-auto" />
                )}
              </div>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-500">Connected</span>
                  <span className={`font-medium ${evidence?.temporal?.connected ? 'text-green-600' : 'text-red-600'}`}>
                    {evidence?.temporal?.connected ? 'Yes' : 'No'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Workflows</span>
                  <span className="font-medium">{evidence?.temporal?.workflow_count ?? '-'}</span>
                </div>
              </div>
            </div>

            {/* Jaeger */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
              <div className="flex items-center gap-2 mb-4">
                <Activity className="w-5 h-5 text-blue-500" />
                <h3 className="font-medium text-gray-900">Jaeger</h3>
                {evidence?.jaeger?.connected ? (
                  <CheckCircle className="w-4 h-4 text-green-500 ml-auto" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-yellow-500 ml-auto" />
                )}
              </div>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-500">Connected</span>
                  <span className={`font-medium ${evidence?.jaeger?.connected ? 'text-green-600' : 'text-red-600'}`}>
                    {evidence?.jaeger?.connected ? 'Yes' : 'No'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Services</span>
                  <span className="font-medium">{evidence?.jaeger?.service_count ?? '-'}</span>
                </div>
              </div>
            </div>

            {/* MLflow */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
              <div className="flex items-center gap-2 mb-4">
                <FlaskConical className="w-5 h-5 text-green-500" />
                <h3 className="font-medium text-gray-900">MLflow</h3>
                {evidence?.mlflow?.connected ? (
                  <CheckCircle className="w-4 h-4 text-green-500 ml-auto" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-yellow-500 ml-auto" />
                )}
              </div>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-500">Experiments</span>
                  <span className="font-medium">{evidence?.mlflow?.experiment_count ?? '-'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Runs</span>
                  <span className="font-medium">{evidence?.mlflow?.run_count ?? '-'}</span>
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {/* External Links */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
        <h3 className="font-medium text-gray-900 mb-4">External Tool UIs</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {EXTERNAL_LINKS.map(link => (
            <a
              key={link.name}
              href={link.url}
              target="_blank"
              rel="noopener noreferrer"
              className="p-4 bg-gray-50 hover:bg-gray-100 rounded-lg transition group"
            >
              <div className="flex items-center gap-2 mb-2">
                <link.icon className="w-5 h-5 text-gray-600" />
                <ExternalLink className="w-3 h-3 text-gray-400 opacity-0 group-hover:opacity-100 transition" />
              </div>
              <p className="font-medium text-gray-900 text-sm">{link.name}</p>
              <p className="text-xs text-gray-500">{link.description}</p>
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
