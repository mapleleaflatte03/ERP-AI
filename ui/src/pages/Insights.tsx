import { useState, useEffect } from 'react';
import { Brain, RefreshCw, Loader2, Plus, AlertTriangle, Lightbulb, CheckCircle2 } from 'lucide-react';
import api from '../lib/api';
import type { Insight } from '../types';

const severityColors: Record<string, string> = {
  high: 'bg-red-100 text-red-700 border-red-200',
  medium: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  low: 'bg-blue-100 text-blue-700 border-blue-200',
  info: 'bg-gray-100 text-gray-700 border-gray-200',
};

const priorityColors: Record<string, string> = {
  high: 'bg-red-500',
  medium: 'bg-yellow-500',
  low: 'bg-blue-500',
};

export default function Insights() {
  const [insights, setInsights] = useState<Insight[]>([]);
  const [selectedInsight, setSelectedInsight] = useState<Insight | null>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [polling, setPolling] = useState(false);
  const [windowDays, setWindowDays] = useState(90);

  const fetchInsights = async () => {
    try {
      const data = await api.listInsights();
      setInsights(data.insights || []);
      if (data.insights?.length > 0 && !selectedInsight) {
        setSelectedInsight(data.insights[0]);
      }
    } catch (err) {
      console.error('Failed to fetch insights:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInsights();
  }, []);

  const handleTrigger = async () => {
    setTriggering(true);
    setPolling(true);
    try {
      const data = await api.triggerInsight(windowDays);
      const insightId = data.insight_id;
      
      // Create a temporary insight to show polling
      setSelectedInsight({
        id: insightId,
        tenant_id: 'default',
        status: 'queued',
        source_window_days: windowDays,
        created_at: new Date().toISOString(),
      });
      
      // Poll for completion
      const pollInterval = setInterval(async () => {
        try {
          const insight = await api.getInsight(insightId);
          setSelectedInsight(insight);
          
          if (insight.status === 'completed' || insight.status === 'failed') {
            clearInterval(pollInterval);
            setPolling(false);
            setTriggering(false);
            fetchInsights();
          }
        } catch {
          // Keep polling
        }
      }, 2000);
      
      // Timeout after 60 seconds
      setTimeout(() => {
        clearInterval(pollInterval);
        setPolling(false);
        setTriggering(false);
        fetchInsights();
      }, 60000);
    } catch (err) {
      console.error('Failed to trigger insight:', err);
      setTriggering(false);
      setPolling(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-amber-600 to-orange-600 rounded-xl shadow-lg p-6 text-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Brain className="w-8 h-8" />
            <div>
              <h2 className="text-xl font-bold">CFO Insights</h2>
              <p className="text-amber-100 text-sm">PR21: AI-powered financial analysis</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <select
              value={windowDays}
              onChange={(e) => setWindowDays(Number(e.target.value))}
              className="px-3 py-2 bg-white/20 rounded-lg text-white text-sm"
            >
              <option value={30}>30 days</option>
              <option value={60}>60 days</option>
              <option value={90}>90 days</option>
              <option value={180}>180 days</option>
            </select>
            <button
              onClick={handleTrigger}
              disabled={triggering}
              className="px-4 py-2 bg-white/20 hover:bg-white/30 rounded-lg transition flex items-center gap-2"
            >
              {triggering ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
              Generate Insights
            </button>
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* List */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-medium text-gray-900">History</h3>
            <button onClick={fetchInsights} className="p-2 hover:bg-gray-100 rounded-lg">
              <RefreshCw className="w-4 h-4 text-gray-500" />
            </button>
          </div>
          
          {loading ? (
            <div className="text-center py-8 text-gray-500">Loading...</div>
          ) : insights.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <Brain className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p>No insights yet</p>
              <p className="text-sm">Click "Generate Insights" to create one</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[400px] overflow-auto">
              {insights.map((i) => (
                <div
                  key={i.id}
                  onClick={() => setSelectedInsight(i)}
                  className={`p-3 rounded-lg cursor-pointer transition ${
                    selectedInsight?.id === i.id
                      ? 'bg-amber-50 border border-amber-200'
                      : 'hover:bg-gray-50 border border-transparent'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">{i.source_window_days} Days</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      i.status === 'completed' ? 'bg-green-100 text-green-700' :
                      i.status === 'failed' ? 'bg-red-100 text-red-700' :
                      'bg-blue-100 text-blue-700'
                    }`}>
                      {i.status}
                    </span>
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {i.created_at ? new Date(i.created_at).toLocaleString() : 'Unknown date'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Detail */}
        <div className="lg:col-span-2 space-y-6">
          {polling && (
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 flex items-center gap-3">
              <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />
              <div>
                <div className="font-medium text-blue-900">Generating insights...</div>
                <div className="text-sm text-blue-700">This may take up to a minute</div>
              </div>
            </div>
          )}
          
          {selectedInsight?.status === 'failed' && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 text-red-600" />
              <div>
                <div className="font-medium text-red-900">Insight generation failed</div>
                <div className="text-sm text-red-700">{selectedInsight.error || 'Unknown error'}</div>
              </div>
            </div>
          )}

          {selectedInsight?.status === 'completed' && (
            <>
              {/* Summary */}
              {selectedInsight.summary && (
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                  <h3 className="font-medium text-gray-900 mb-3">Executive Summary</h3>
                  <p className="text-gray-700 whitespace-pre-wrap">{selectedInsight.summary}</p>
                </div>
              )}

              {/* Top Findings */}
              {selectedInsight.top_findings && selectedInsight.top_findings.length > 0 && (
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                  <h3 className="font-medium text-gray-900 mb-4 flex items-center gap-2">
                    <AlertTriangle className="w-5 h-5 text-amber-500" />
                    Top Findings
                  </h3>
                  <div className="grid gap-4">
                    {selectedInsight.top_findings.map((finding, idx) => (
                      <div 
                        key={idx} 
                        className={`p-4 rounded-lg border ${severityColors[finding.severity] || severityColors.info}`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="font-medium">{finding.title}</div>
                          <span className="text-xs uppercase font-semibold">{finding.severity}</span>
                        </div>
                        <p className="text-sm mt-2 opacity-80">{finding.description}</p>
                        {finding.metric_value && (
                          <div className="text-xs mt-2 font-mono">
                            Value: {finding.metric_value}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommendations */}
              {selectedInsight.recommendations && selectedInsight.recommendations.length > 0 && (
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                  <h3 className="font-medium text-gray-900 mb-4 flex items-center gap-2">
                    <Lightbulb className="w-5 h-5 text-yellow-500" />
                    Recommendations
                  </h3>
                  <div className="space-y-3">
                    {selectedInsight.recommendations.map((rec, idx) => (
                      <div key={idx} className="flex gap-3">
                        <div className={`w-1 rounded-full flex-shrink-0 ${priorityColors[rec.priority] || 'bg-gray-400'}`} />
                        <div>
                          <div className="font-medium text-gray-900">{rec.action}</div>
                          <div className="text-sm text-gray-600 mt-1">{rec.rationale}</div>
                          {rec.expected_impact && (
                            <div className="text-xs text-green-600 mt-1 flex items-center gap-1">
                              <CheckCircle2 className="w-3 h-3" />
                              Expected: {rec.expected_impact}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* References */}
              {selectedInsight.references && selectedInsight.references.length > 0 && (
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                  <h3 className="font-medium text-gray-900 mb-4">Supporting Data</h3>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    {selectedInsight.references.map((ref, idx) => (
                      <div key={idx} className="p-3 bg-gray-50 rounded-lg text-sm">
                        <div className="text-gray-500 text-xs">{ref.type}</div>
                        <div className="font-medium truncate">{ref.id}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {!selectedInsight && !polling && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center text-gray-500">
              <Brain className="w-16 h-16 mx-auto mb-4 opacity-50" />
              <p>Select an insight to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
