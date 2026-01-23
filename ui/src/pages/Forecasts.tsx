import { useState, useEffect } from 'react';
import { TrendingUp, RefreshCw, Loader2, Plus, Calendar } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import api from '../lib/api';
import type { Forecast } from '../types';

export default function Forecasts() {
  const [forecasts, setForecasts] = useState<Forecast[]>([]);
  const [selectedForecast, setSelectedForecast] = useState<Forecast | null>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [windowDays, setWindowDays] = useState(30);

  const fetchForecasts = async () => {
    try {
      const data = await api.listForecasts();
      setForecasts(data.forecasts || []);
      if (data.forecasts?.length > 0 && !selectedForecast) {
        setSelectedForecast(data.forecasts[0]);
      }
    } catch (err) {
      console.error('Failed to fetch forecasts:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchForecasts();
  }, []);

  const handleTrigger = async () => {
    setTriggering(true);
    try {
      await api.triggerForecast(windowDays);
      await new Promise(r => setTimeout(r, 2000));
      await fetchForecasts();
    } catch (err) {
      console.error('Failed to trigger forecast:', err);
    } finally {
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

  interface DailyForecast {
    date: string;
    inflow: number;
    outflow: number;
    net: number;
  }

  const chartData = selectedForecast?.daily_forecast?.map((day: DailyForecast, index: number, arr: DailyForecast[]) => ({
    date: day.date,
    net: day.net,
    cumulative: arr.slice(0, index + 1).reduce((sum, d) => sum + d.net, 0),
  })) || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-indigo-600 rounded-xl shadow-lg p-6 text-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <TrendingUp className="w-8 h-8" />
            <div>
              <h2 className="text-xl font-bold">Cashflow Forecasts</h2>
              <p className="text-blue-100 text-sm">PR20: Predict future cash positions</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <select
              value={windowDays}
              onChange={(e) => setWindowDays(Number(e.target.value))}
              className="px-3 py-2 bg-white/20 rounded-lg text-white text-sm"
            >
              <option value={7}>7 days</option>
              <option value={14}>14 days</option>
              <option value={30}>30 days</option>
              <option value={60}>60 days</option>
              <option value={90}>90 days</option>
            </select>
            <button
              onClick={handleTrigger}
              disabled={triggering}
              className="px-4 py-2 bg-white/20 hover:bg-white/30 rounded-lg transition flex items-center gap-2"
            >
              {triggering ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
              New Forecast
            </button>
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Forecast List */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-medium text-gray-900">Recent Forecasts</h3>
            <button onClick={fetchForecasts} className="p-2 hover:bg-gray-100 rounded-lg">
              <RefreshCw className="w-4 h-4 text-gray-500" />
            </button>
          </div>
          
          {loading ? (
            <div className="text-center py-8 text-gray-500">Loading...</div>
          ) : forecasts.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <Calendar className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p>No forecasts yet</p>
              <p className="text-sm">Click "New Forecast" to generate one</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[400px] overflow-auto">
              {forecasts.map((f) => (
                <div
                  key={f.id}
                  onClick={() => setSelectedForecast(f)}
                  className={`p-3 rounded-lg cursor-pointer transition ${
                    selectedForecast?.id === f.id
                      ? 'bg-blue-50 border border-blue-200'
                      : 'hover:bg-gray-50 border border-transparent'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">{f.window_days} Days</span>
                    <span className={`text-sm font-bold ${f.net_position >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {formatCurrency(f.net_position)}
                    </span>
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {f.created_at ? new Date(f.created_at).toLocaleString() : 'Unknown date'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Forecast Detail */}
        <div className="lg:col-span-2 space-y-6">
          {selectedForecast ? (
            <>
              {/* Summary Cards */}
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-green-50 rounded-xl p-4 border border-green-200">
                  <div className="text-xs text-green-600 mb-1">Total Inflow</div>
                  <div className="text-xl font-bold text-green-700">{formatCurrency(selectedForecast.total_inflow)}</div>
                </div>
                <div className="bg-red-50 rounded-xl p-4 border border-red-200">
                  <div className="text-xs text-red-600 mb-1">Total Outflow</div>
                  <div className="text-xl font-bold text-red-700">{formatCurrency(Math.abs(selectedForecast.total_outflow))}</div>
                </div>
                <div className={`rounded-xl p-4 border ${selectedForecast.net_position >= 0 ? 'bg-blue-50 border-blue-200' : 'bg-orange-50 border-orange-200'}`}>
                  <div className={`text-xs mb-1 ${selectedForecast.net_position >= 0 ? 'text-blue-600' : 'text-orange-600'}`}>Net Position</div>
                  <div className={`text-xl font-bold ${selectedForecast.net_position >= 0 ? 'text-blue-700' : 'text-orange-700'}`}>
                    {formatCurrency(selectedForecast.net_position)}
                  </div>
                </div>
              </div>

              {/* Chart */}
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <h3 className="font-medium text-gray-900 mb-4">Cashflow Projection</h3>
                {chartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                      <Tooltip />
                      <Legend />
                      <Line type="monotone" dataKey="net" stroke="#3b82f6" name="Daily Net" strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="cumulative" stroke="#10b981" name="Cumulative" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-[300px] flex items-center justify-center text-gray-400">
                    No daily forecast data available
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center text-gray-500">
              <TrendingUp className="w-16 h-16 mx-auto mb-4 opacity-50" />
              <p>Select a forecast to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
