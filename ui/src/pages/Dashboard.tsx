import { useEffect, useState } from 'react';
import { ExternalLink, RefreshCw, Copy, Check, Activity } from 'lucide-react';
import api from '../lib/api';

const externalLinks = [
  { name: 'Temporal UI', url: 'http://localhost:8088', description: 'Workflow management' },
  { name: 'Jaeger', url: 'http://localhost:16686', description: 'Distributed tracing' },
  { name: 'MinIO Console', url: 'http://localhost:9001', description: 'Object storage' },
  { name: 'Qdrant Dashboard', url: 'http://localhost:6333/dashboard', description: 'Vector database' },
  { name: 'MLflow', url: 'http://localhost:5001', description: 'ML experiment tracking' },
  { name: 'Keycloak', url: 'http://localhost:8180', description: 'Identity management' },
  { name: 'Kong Gateway', url: 'http://localhost:8002', description: 'API gateway' },
];

interface Counters {
  extracted_invoices: number;
  journal_proposals: number;
  approvals: number;
  ledger_entries: number;
  ledger_lines: number;
  cashflow_forecasts: number;
  scenario_simulations: number;
  cfo_insights: number;
}

export default function Dashboard() {
  const [counters, setCounters] = useState<Counters | null>(null);
  const [health, setHealth] = useState<string>('checking...');
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  const verifyCommand = `cd /root/erp-ai && bash scripts/full_system_verify.sh`;

  const fetchData = async () => {
    setLoading(true);
    try {
      const healthRes = await api.getHealth();
      setHealth(healthRes.status || 'ok');
      
      // Try to fetch evidence for counters
      try {
        const evidenceRes = await api.getEvidence();
        if (evidenceRes.postgres) {
          setCounters(evidenceRes.postgres);
        }
      } catch {
        // Evidence endpoint may not exist yet
        setCounters(null);
      }
    } catch (err) {
      setHealth('error');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const copyCommand = () => {
    navigator.clipboard.writeText(verifyCommand);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Health Status */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">System Health</h2>
          <button
            onClick={fetchData}
            disabled={loading}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition"
          >
            <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
        <div className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full ${health === 'ok' ? 'bg-green-500' : health === 'error' ? 'bg-red-500' : 'bg-yellow-500'}`} />
          <span className="text-gray-700 font-medium capitalize">{health}</span>
        </div>
      </div>

      {/* Counters Grid */}
      {counters && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Object.entries(counters).map(([key, value]) => (
            <div key={key} className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
              <div className="text-2xl font-bold text-gray-900">{value}</div>
              <div className="text-sm text-gray-500 capitalize">{key.replace(/_/g, ' ')}</div>
            </div>
          ))}
        </div>
      )}

      {/* Full Verify Command */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-xl shadow-lg p-6 text-white">
        <div className="flex items-center gap-3 mb-3">
          <Activity className="w-6 h-6" />
          <h2 className="text-lg font-semibold">Run Full System Verify</h2>
        </div>
        <p className="text-blue-100 text-sm mb-4">
          Execute this command to run all tests and collect evidence from every integrated tool.
        </p>
        <div className="bg-black/20 rounded-lg p-3 flex items-center justify-between">
          <code className="text-sm text-blue-100 font-mono">{verifyCommand}</code>
          <button
            onClick={copyCommand}
            className="p-2 hover:bg-white/10 rounded transition"
          >
            {copied ? <Check className="w-5 h-5" /> : <Copy className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* External Links */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">External Services</h2>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {externalLinks.map((link) => (
            <a
              key={link.name}
              href={link.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition group"
            >
              <div>
                <div className="font-medium text-gray-900 group-hover:text-blue-600">{link.name}</div>
                <div className="text-sm text-gray-500">{link.description}</div>
              </div>
              <ExternalLink className="w-5 h-5 text-gray-400 group-hover:text-blue-500" />
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
