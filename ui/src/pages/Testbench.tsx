import { useState, useEffect } from 'react';
import { 
  Play, CheckCircle, XCircle, AlertTriangle, Loader2, RefreshCw,
  Database, HardDrive, Brain, GitBranch, Shield, FileText, 
  Activity, BarChart3, FlaskConical, Key, Network
} from 'lucide-react';
import api from '../lib/api';

interface Tool {
  id: string;
  name: string;
  description: string;
}

interface TestResult {
  tool: string;
  name: string;
  passed: boolean;
  latency_ms: number;
  summary: string;
  evidence: Record<string, unknown>;
  trace_id?: string;
  warning?: string;
}

const TOOL_ICONS: Record<string, React.ElementType> = {
  keycloak: Key,
  kong: Network,
  postgres: Database,
  minio: HardDrive,
  qdrant: Brain,
  temporal: GitBranch,
  opa: Shield,
  ocr: FileText,
  jaeger: Activity,
  metrics: BarChart3,
  mlflow: FlaskConical,
};

export default function Testbench() {
  const [tools, setTools] = useState<Tool[]>([]);
  const [results, setResults] = useState<Record<string, TestResult>>({});
  const [running, setRunning] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTools();
  }, []);

  const fetchTools = async () => {
    try {
      const data = await api.getTestbenchTools();
      setTools(data.tools || []);
    } catch (err) {
      console.error('Failed to fetch tools:', err);
    } finally {
      setLoading(false);
    }
  };

  const runTest = async (toolId: string) => {
    setRunning(prev => ({ ...prev, [toolId]: true }));
    try {
      const result = await api.runTestbenchTool(toolId);
      setResults(prev => ({ ...prev, [toolId]: result }));
    } catch (err) {
      console.error(`Failed to test ${toolId}:`, err);
      setResults(prev => ({
        ...prev,
        [toolId]: {
          tool: toolId,
          name: toolId,
          passed: false,
          latency_ms: 0,
          summary: `Test failed: ${err}`,
          evidence: { error: String(err) }
        }
      }));
    } finally {
      setRunning(prev => ({ ...prev, [toolId]: false }));
    }
  };

  const runAllTests = async () => {
    for (const tool of tools) {
      await runTest(tool.id);
    }
  };

  const getStatusIcon = (toolId: string) => {
    if (running[toolId]) {
      return <Loader2 className="w-5 h-5 animate-spin text-blue-500" />;
    }
    const result = results[toolId];
    if (!result) {
      return <div className="w-5 h-5 rounded-full bg-gray-200" />;
    }
    if (result.passed) {
      return <CheckCircle className="w-5 h-5 text-green-500" />;
    }
    if (result.warning) {
      return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
    }
    return <XCircle className="w-5 h-5 text-red-500" />;
  };

  const passedCount = Object.values(results).filter(r => r.passed).length;
  const failedCount = Object.values(results).filter(r => !r.passed && !r.warning).length;
  const warnCount = Object.values(results).filter(r => r.warning).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-slate-800 to-slate-700 rounded-xl shadow-lg p-6 text-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <FlaskConical className="w-8 h-8" />
            <div>
              <h2 className="text-xl font-bold">Tool Testbench</h2>
              <p className="text-slate-300 text-sm">Verify each infrastructure component</p>
            </div>
          </div>
          <button
            onClick={runAllTests}
            disabled={Object.values(running).some(Boolean)}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg flex items-center gap-2 transition disabled:opacity-50"
          >
            {Object.values(running).some(Boolean) ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            Run All Tests
          </button>
        </div>
        
        {/* Summary Stats */}
        {Object.keys(results).length > 0 && (
          <div className="mt-4 flex gap-6 text-sm">
            <div className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-green-400" />
              <span>{passedCount} Passed</span>
            </div>
            <div className="flex items-center gap-2">
              <XCircle className="w-4 h-4 text-red-400" />
              <span>{failedCount} Failed</span>
            </div>
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-yellow-400" />
              <span>{warnCount} Warnings</span>
            </div>
          </div>
        )}
      </div>

      {/* Tools Grid */}
      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading tools...</div>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {tools.map(tool => {
            const Icon = TOOL_ICONS[tool.id] || FlaskConical;
            const result = results[tool.id];
            
            return (
              <div
                key={tool.id}
                className={`bg-white rounded-xl border shadow-sm overflow-hidden ${
                  result?.passed ? 'border-green-200' : 
                  result && !result.passed && !result.warning ? 'border-red-200' :
                  result?.warning ? 'border-yellow-200' : 'border-gray-200'
                }`}
              >
                {/* Tool Header */}
                <div className="p-4 border-b border-gray-100">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`p-2 rounded-lg ${
                        result?.passed ? 'bg-green-100 text-green-600' :
                        result && !result.passed ? 'bg-red-100 text-red-600' :
                        'bg-gray-100 text-gray-600'
                      }`}>
                        <Icon className="w-5 h-5" />
                      </div>
                      <div>
                        <h3 className="font-medium text-gray-900">{tool.name}</h3>
                        <p className="text-xs text-gray-500">{tool.description}</p>
                      </div>
                    </div>
                    {getStatusIcon(tool.id)}
                  </div>
                </div>
                
                {/* Test Button / Result */}
                <div className="p-4">
                  {!result ? (
                    <button
                      onClick={() => runTest(tool.id)}
                      disabled={running[tool.id]}
                      className="w-full py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg transition flex items-center justify-center gap-2"
                    >
                      {running[tool.id] ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Play className="w-4 h-4" />
                      )}
                      Run Test
                    </button>
                  ) : (
                    <div className="space-y-3">
                      {/* Summary */}
                      <div className={`text-sm p-2 rounded ${
                        result.passed ? 'bg-green-50 text-green-700' :
                        result.warning ? 'bg-yellow-50 text-yellow-700' :
                        'bg-red-50 text-red-700'
                      }`}>
                        {result.summary}
                      </div>
                      
                      {/* Latency */}
                      <div className="flex items-center justify-between text-xs text-gray-500">
                        <span>Latency: {result.latency_ms.toFixed(1)}ms</span>
                        {result.trace_id && (
                          <span className="font-mono text-xs">{result.trace_id.slice(0, 8)}...</span>
                        )}
                      </div>
                      
                      {/* Warning */}
                      {result.warning && (
                        <div className="text-xs text-yellow-600 bg-yellow-50 p-2 rounded">
                          ⚠️ {result.warning}
                        </div>
                      )}
                      
                      {/* Evidence (collapsible) */}
                      <details className="text-xs">
                        <summary className="cursor-pointer text-gray-500 hover:text-gray-700">
                          View Evidence JSON
                        </summary>
                        <pre className="mt-2 p-2 bg-gray-50 rounded overflow-auto max-h-40 text-xs">
                          {JSON.stringify(result.evidence, null, 2)}
                        </pre>
                      </details>
                      
                      {/* Rerun */}
                      <button
                        onClick={() => runTest(tool.id)}
                        disabled={running[tool.id]}
                        className="w-full py-1.5 text-xs bg-gray-100 hover:bg-gray-200 rounded flex items-center justify-center gap-1"
                      >
                        <RefreshCw className="w-3 h-3" />
                        Rerun
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* External Links */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
        <h3 className="font-medium text-gray-900 mb-4">External Tool UIs</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
          {[
            { name: 'Temporal', url: 'http://localhost:8088', icon: GitBranch },
            { name: 'Jaeger', url: 'http://localhost:16686', icon: Activity },
            { name: 'Grafana', url: 'http://localhost:3001', icon: BarChart3 },
            { name: 'MinIO', url: 'http://localhost:9001', icon: HardDrive },
            { name: 'Qdrant', url: 'http://localhost:6333/dashboard', icon: Brain },
            { name: 'MLflow', url: 'http://localhost:5000', icon: FlaskConical },
          ].map(link => (
            <a
              key={link.name}
              href={link.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 p-3 bg-gray-50 hover:bg-gray-100 rounded-lg transition text-sm"
            >
              <link.icon className="w-4 h-4 text-gray-500" />
              <span>{link.name}</span>
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
