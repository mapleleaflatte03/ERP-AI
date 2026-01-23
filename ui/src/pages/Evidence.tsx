import { useState, useEffect } from 'react';
import { Shield, RefreshCw, Database, HardDrive, Box, GitBranch, Activity, FlaskConical, CheckCircle2, XCircle, ExternalLink } from 'lucide-react';
import api from '../lib/api';

interface EvidenceState {
  postgres: Record<string, number> | null;
  minio: { sample_keys: string[] } | null;
  qdrant: { points_count: number } | null;
  temporal: { completed_jobs: number } | null;
  jaeger: { services: string[] } | null;
  mlflow: { runs_count: number } | null;
}

export default function Evidence() {
  const [evidence, setEvidence] = useState<EvidenceState>({
    postgres: null,
    minio: null,
    qdrant: null,
    temporal: null,
    jaeger: null,
    mlflow: null,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchEvidence = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getEvidence();
      setEvidence(data);
    } catch (err) {
      setError('Failed to fetch evidence. Make sure the API endpoint is available.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvidence();
  }, []);

  const EvidenceCard = ({ title, icon: Icon, status, children, link }: {
    title: string;
    icon: React.ElementType;
    status: 'pass' | 'warn' | 'fail' | 'loading';
    children: React.ReactNode;
    link?: string;
  }) => (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
            status === 'pass' ? 'bg-green-100' :
            status === 'warn' ? 'bg-yellow-100' :
            status === 'fail' ? 'bg-red-100' : 'bg-gray-100'
          }`}>
            <Icon className={`w-5 h-5 ${
              status === 'pass' ? 'text-green-600' :
              status === 'warn' ? 'text-yellow-600' :
              status === 'fail' ? 'text-red-600' : 'text-gray-400'
            }`} />
          </div>
          <div>
            <h3 className="font-medium text-gray-900">{title}</h3>
            <div className="flex items-center gap-1">
              {status === 'pass' && <CheckCircle2 className="w-3 h-3 text-green-500" />}
              {status === 'fail' && <XCircle className="w-3 h-3 text-red-500" />}
              <span className={`text-xs ${
                status === 'pass' ? 'text-green-600' :
                status === 'warn' ? 'text-yellow-600' :
                status === 'fail' ? 'text-red-600' : 'text-gray-500'
              }`}>
                {status === 'pass' ? 'Connected' : status === 'warn' ? 'Partial' : status === 'fail' ? 'Not Available' : 'Loading...'}
              </span>
            </div>
          </div>
        </div>
        {link && (
          <a
            href={link}
            target="_blank"
            rel="noopener noreferrer"
            className="p-2 text-gray-400 hover:text-blue-500 hover:bg-blue-50 rounded-lg transition"
          >
            <ExternalLink className="w-4 h-4" />
          </a>
        )}
      </div>
      <div className="space-y-2 text-sm">
        {children}
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-green-600 to-teal-600 rounded-xl shadow-lg p-6 text-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Shield className="w-8 h-8" />
            <div>
              <h2 className="text-xl font-bold">System Evidence</h2>
              <p className="text-green-100 text-sm">Verify tool integrations are working</p>
            </div>
          </div>
          <button
            onClick={fetchEvidence}
            disabled={loading}
            className="px-4 py-2 bg-white/20 hover:bg-white/30 rounded-lg transition flex items-center gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      )}

      {/* Evidence Grid */}
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* Postgres */}
        <EvidenceCard
          title="PostgreSQL"
          icon={Database}
          status={evidence.postgres ? 'pass' : loading ? 'loading' : 'fail'}
        >
          {evidence.postgres ? (
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(evidence.postgres).map(([key, val]) => (
                <div key={key} className="flex justify-between">
                  <span className="text-gray-500 text-xs">{key.replace(/_/g, ' ')}:</span>
                  <span className="font-mono text-xs">{val}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-gray-400">Loading counters...</div>
          )}
        </EvidenceCard>

        {/* MinIO */}
        <EvidenceCard
          title="MinIO Object Storage"
          icon={HardDrive}
          status={evidence.minio?.sample_keys?.length ? 'pass' : loading ? 'loading' : 'warn'}
          link="http://localhost:9001"
        >
          {evidence.minio?.sample_keys?.length ? (
            <div>
              <div className="text-xs text-gray-500 mb-1">Sample objects:</div>
              {evidence.minio.sample_keys.slice(0, 3).map((key, i) => (
                <div key={i} className="font-mono text-xs text-gray-600 truncate">{key}</div>
              ))}
            </div>
          ) : (
            <div className="text-gray-400 text-xs">No objects found</div>
          )}
        </EvidenceCard>

        {/* Qdrant */}
        <EvidenceCard
          title="Qdrant Vectors"
          icon={Box}
          status={(evidence.qdrant?.points_count || 0) > 0 ? 'pass' : loading ? 'loading' : 'warn'}
          link="http://localhost:6333/dashboard"
        >
          <div className="flex items-center justify-between">
            <span className="text-gray-500">Points count:</span>
            <span className="font-mono font-bold">{evidence.qdrant?.points_count || 0}</span>
          </div>
        </EvidenceCard>

        {/* Temporal */}
        <EvidenceCard
          title="Temporal Workflows"
          icon={GitBranch}
          status={(evidence.temporal?.completed_jobs || 0) > 0 ? 'pass' : loading ? 'loading' : 'warn'}
          link="http://localhost:8088"
        >
          <div className="flex items-center justify-between">
            <span className="text-gray-500">Completed jobs:</span>
            <span className="font-mono font-bold">{evidence.temporal?.completed_jobs || 0}</span>
          </div>
        </EvidenceCard>

        {/* Jaeger */}
        <EvidenceCard
          title="Jaeger Tracing"
          icon={Activity}
          status={evidence.jaeger?.services?.length ? 'pass' : loading ? 'loading' : 'warn'}
          link="http://localhost:16686"
        >
          {evidence.jaeger?.services?.length ? (
            <div>
              <div className="text-xs text-gray-500 mb-1">Services:</div>
              <div className="flex flex-wrap gap-1">
                {evidence.jaeger.services.slice(0, 5).map((svc, i) => (
                  <span key={i} className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded-full">{svc}</span>
                ))}
              </div>
            </div>
          ) : (
            <div className="text-gray-400 text-xs">No services found</div>
          )}
        </EvidenceCard>

        {/* MLflow */}
        <EvidenceCard
          title="MLflow Tracking"
          icon={FlaskConical}
          status={(evidence.mlflow?.runs_count || 0) > 0 ? 'pass' : loading ? 'loading' : 'warn'}
          link="http://localhost:5001"
        >
          <div className="flex items-center justify-between">
            <span className="text-gray-500">Experiment runs:</span>
            <span className="font-mono font-bold">{evidence.mlflow?.runs_count || 0}</span>
          </div>
        </EvidenceCard>
      </div>

      {/* CLI Command */}
      <div className="bg-gray-900 rounded-xl p-6">
        <h3 className="text-white font-medium mb-3">Full System Verification (CLI)</h3>
        <p className="text-gray-400 text-sm mb-4">
          Run this command to execute complete end-to-end verification with detailed evidence output:
        </p>
        <div className="bg-black/50 rounded-lg p-4 font-mono text-sm text-green-400 overflow-x-auto">
          cd /root/erp-ai && bash scripts/full_system_verify.sh
        </div>
      </div>
    </div>
  );
}
