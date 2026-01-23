import { useState, useEffect } from 'react';
import { FlaskConical, RefreshCw, Loader2, Plus } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import api from '../lib/api';
import type { Simulation } from '../types';

export default function Simulations() {
  const [simulations, setSimulations] = useState<Simulation[]>([]);
  const [selectedSim, setSelectedSim] = useState<Simulation | null>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  
  const [windowDays, setWindowDays] = useState(30);
  const [revMult, setRevMult] = useState(1.0);
  const [costMult, setCostMult] = useState(1.0);
  const [delayDays, setDelayDays] = useState(0);

  const fetchSimulations = async () => {
    try {
      const data = await api.listSimulations();
      setSimulations(data.simulations || []);
      if (data.simulations?.length > 0 && !selectedSim) {
        setSelectedSim(data.simulations[0]);
      }
    } catch (err) {
      console.error('Failed to fetch simulations:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSimulations();
  }, []);

  const handleTrigger = async () => {
    setTriggering(true);
    try {
      const data = await api.triggerSimulation(windowDays, revMult, costMult, delayDays);
      const simId = data.simulation_id;
      
      const pollInterval = setInterval(async () => {
        try {
          const sim = await api.getSimulation(simId);
          if (sim.status === 'completed' || sim.result) {
            clearInterval(pollInterval);
            setSelectedSim(sim);
            fetchSimulations();
            setTriggering(false);
          }
        } catch {
          // Keep polling
        }
      }, 1000);
      
      setTimeout(() => {
        clearInterval(pollInterval);
        setTriggering(false);
        fetchSimulations();
      }, 30000);
    } catch (err) {
      console.error('Failed to trigger simulation:', err);
      setTriggering(false);
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const chartData = selectedSim ? [
    { name: 'Baseline', value: selectedSim.baseline_net || 0 },
    { name: 'Projected', value: selectedSim.projected_net || 0 },
  ] : [];

  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-r from-purple-600 to-pink-600 rounded-xl shadow-lg p-6 text-white">
        <div className="flex items-center gap-3">
          <FlaskConical className="w-8 h-8" />
          <div>
            <h2 className="text-xl font-bold">Scenario Simulations</h2>
            <p className="text-purple-100 text-sm">PR20: What-if analysis for cashflow</p>
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        <div className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <h3 className="font-medium text-gray-900 mb-4">New Simulation</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Window Days</label>
                <select
                  value={windowDays}
                  onChange={(e) => setWindowDays(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  <option value={7}>7 days</option>
                  <option value={14}>14 days</option>
                  <option value={30}>30 days</option>
                  <option value={60}>60 days</option>
                  <option value={90}>90 days</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Revenue Multiplier</label>
                <input
                  type="number"
                  step="0.1"
                  value={revMult}
                  onChange={(e) => setRevMult(parseFloat(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Cost Multiplier</label>
                <input
                  type="number"
                  step="0.1"
                  value={costMult}
                  onChange={(e) => setCostMult(parseFloat(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Payment Delay (days)</label>
                <input
                  type="number"
                  value={delayDays}
                  onChange={(e) => setDelayDays(parseInt(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                />
              </div>
              <button
                onClick={handleTrigger}
                disabled={triggering}
                className="w-full py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition flex items-center justify-center gap-2"
              >
                {triggering ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                Run Simulation
              </button>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-medium text-gray-900">History</h3>
              <button onClick={fetchSimulations} className="p-2 hover:bg-gray-100 rounded-lg">
                <RefreshCw className="w-4 h-4 text-gray-500" />
              </button>
            </div>
            
            {loading ? (
              <div className="text-center py-8 text-gray-500">Loading...</div>
            ) : simulations.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <FlaskConical className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>No simulations yet</p>
              </div>
            ) : (
              <div className="space-y-2 max-h-[300px] overflow-auto">
                {simulations.map((s) => (
                  <div
                    key={s.id}
                    onClick={() => setSelectedSim(s)}
                    className={`p-3 rounded-lg cursor-pointer transition ${
                      selectedSim?.id === s.id
                        ? 'bg-purple-50 border border-purple-200'
                        : 'hover:bg-gray-50 border border-transparent'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium truncate">{s.scenario_name || 'Unnamed'}</span>
                      <span className={`text-sm font-bold ${(s.percent_change || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {(s.percent_change || 0) >= 0 ? '+' : ''}{(s.percent_change || 0).toFixed(1)}%
                      </span>
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      {s.created_at ? new Date(s.created_at).toLocaleString() : 'Unknown date'}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="lg:col-span-2 space-y-6">
          {selectedSim ? (
            <>
              <div className="grid grid-cols-4 gap-4">
                <div className="bg-gray-50 rounded-xl p-4 border border-gray-200">
                  <div className="text-xs text-gray-500 mb-1">Baseline</div>
                  <div className="text-lg font-bold text-gray-700">{formatCurrency(selectedSim.baseline_net || 0)}</div>
                </div>
                <div className="bg-purple-50 rounded-xl p-4 border border-purple-200">
                  <div className="text-xs text-purple-600 mb-1">Projected</div>
                  <div className="text-lg font-bold text-purple-700">{formatCurrency(selectedSim.projected_net || 0)}</div>
                </div>
                <div className={`rounded-xl p-4 border ${(selectedSim.delta || 0) >= 0 ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
                  <div className={`text-xs mb-1 ${(selectedSim.delta || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>Delta</div>
                  <div className={`text-lg font-bold ${(selectedSim.delta || 0) >= 0 ? 'text-green-700' : 'text-red-700'}`}>
                    {formatCurrency(selectedSim.delta || 0)}
                  </div>
                </div>
                <div className={`rounded-xl p-4 border ${(selectedSim.percent_change || 0) >= 0 ? 'bg-blue-50 border-blue-200' : 'bg-orange-50 border-orange-200'}`}>
                  <div className={`text-xs mb-1 ${(selectedSim.percent_change || 0) >= 0 ? 'text-blue-600' : 'text-orange-600'}`}>Change</div>
                  <div className={`text-lg font-bold ${(selectedSim.percent_change || 0) >= 0 ? 'text-blue-700' : 'text-orange-700'}`}>
                    {(selectedSim.percent_change || 0) >= 0 ? '+' : ''}{(selectedSim.percent_change || 0).toFixed(1)}%
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <h3 className="font-medium text-gray-900 mb-4">Comparison</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="value" fill="#8b5cf6" name="Net Position" />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {selectedSim.assumptions && (
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                  <h3 className="font-medium text-gray-900 mb-4">Assumptions</h3>
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <span className="text-gray-500">Revenue Multiplier:</span>
                      <span className="ml-2 font-medium">{selectedSim.assumptions.revenue_multiplier || 1.0}x</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Cost Multiplier:</span>
                      <span className="ml-2 font-medium">{selectedSim.assumptions.cost_multiplier || 1.0}x</span>
                    </div>
                    <div>
                      <span className="text-gray-500">Payment Delay:</span>
                      <span className="ml-2 font-medium">{selectedSim.assumptions.payment_delay_days || 0} days</span>
                    </div>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center text-gray-500">
              <FlaskConical className="w-16 h-16 mx-auto mb-4 opacity-50" />
              <p>Select a simulation to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
