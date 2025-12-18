import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  Activity,
  Clock,
  Play,
  Square,
  RefreshCw,
  CheckCircle2,
  XCircle,
  AlertCircle
} from 'lucide-react';
import { monitoringApi } from '@/services/api';
import { formatDistanceToNow } from 'date-fns';

export default function MonitoringPage() {
  const queryClient = useQueryClient();
  const [selectedSeverity, setSelectedSeverity] = useState<string>('low');

  // Fetch monitoring status
  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ['monitoring-status'],
    queryFn: monitoringApi.getStatus,
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  // Fetch targets
  const { data: targets = [], isLoading: targetsLoading } = useQuery({
    queryKey: ['monitoring-targets'],
    queryFn: monitoringApi.getTargets,
    refetchInterval: 10000, // Refresh every 10 seconds
  });

  // Fetch alerts
  const { data: alerts = [], isLoading: alertsLoading } = useQuery({
    queryKey: ['monitoring-alerts', selectedSeverity],
    queryFn: () => monitoringApi.getAlerts({ min_severity: selectedSeverity }),
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  // Start monitoring mutation
  const startMutation = useMutation({
    mutationFn: monitoringApi.start,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['monitoring-status'] });
    },
  });

  // Stop monitoring mutation
  const stopMutation = useMutation({
    mutationFn: monitoringApi.stop,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['monitoring-status'] });
    },
  });

  // Enable/disable target mutations
  const enableMutation = useMutation({
    mutationFn: (name: string) => monitoringApi.enableTarget(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['monitoring-targets'] });
    },
  });

  const disableMutation = useMutation({
    mutationFn: (name: string) => monitoringApi.disableTarget(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['monitoring-targets'] });
    },
  });

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'text-red-400 bg-red-500/20';
      case 'high':
        return 'text-orange-400 bg-orange-500/20';
      case 'medium':
        return 'text-yellow-400 bg-yellow-500/20';
      case 'low':
        return 'text-blue-400 bg-blue-500/20';
      default:
        return 'text-gray-400 bg-gray-500/20';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Proactive Monitoring</h1>
        <div className="flex gap-2">
          {status?.running ? (
            <button
              onClick={() => stopMutation.mutate()}
              disabled={stopMutation.isPending}
              className="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded-lg transition-colors flex items-center gap-2"
            >
              <Square className="w-4 h-4" />
              Stop Monitoring
            </button>
          ) : (
            <button
              onClick={() => startMutation.mutate()}
              disabled={startMutation.isPending}
              className="bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-lg transition-colors flex items-center gap-2"
            >
              <Play className="w-4 h-4" />
              Start Monitoring
            </button>
          )}
          <button
            onClick={() => queryClient.invalidateQueries()}
            className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center gap-3">
            <div className={`w-12 h-12 ${status?.running ? 'bg-green-500/20' : 'bg-gray-500/20'} rounded-lg flex items-center justify-center`}>
              <Activity className={`w-6 h-6 ${status?.running ? 'text-green-400' : 'text-gray-400'}`} />
            </div>
            <div>
              <p className="text-gray-400 text-sm">Status</p>
              <p className="text-2xl font-bold">{statusLoading ? '...' : status?.running ? 'Running' : 'Stopped'}</p>
            </div>
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-blue-500/20 rounded-lg flex items-center justify-center">
              <Clock className="w-6 h-6 text-blue-400" />
            </div>
            <div>
              <p className="text-gray-400 text-sm">Active Targets</p>
              <p className="text-2xl font-bold">{statusLoading ? '...' : status?.enabled_targets || 0}</p>
            </div>
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-red-500/20 rounded-lg flex items-center justify-center">
              <AlertTriangle className="w-6 h-6 text-red-400" />
            </div>
            <div>
              <p className="text-gray-400 text-sm">Recent Alerts</p>
              <p className="text-2xl font-bold">{statusLoading ? '...' : status?.recent_alerts || 0}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Monitoring Targets */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-bold mb-4">Monitoring Targets</h2>
        {targetsLoading ? (
          <div className="text-center text-gray-400 py-12">Loading targets...</div>
        ) : targets.length === 0 ? (
          <div className="text-center text-gray-400 py-12">
            <p>No monitoring targets configured yet.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {targets.map((target) => (
              <div
                key={target.name}
                className="bg-gray-900/50 border border-gray-700 rounded-lg p-4 flex items-center justify-between"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="font-semibold">{target.name}</h3>
                    <span className={`px-2 py-1 rounded text-xs ${getSeverityColor(target.severity_threshold)}`}>
                      {target.severity_threshold}
                    </span>
                    <span className="text-xs text-gray-500">
                      {target.query_type}
                    </span>
                  </div>
                  <p className="text-sm text-gray-400 font-mono">{target.query}</p>
                  <div className="text-xs text-gray-500 mt-2">
                    Check every {target.check_interval}s | Methods: {target.detection_methods.join(', ')}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {target.enabled ? (
                    <>
                      <CheckCircle2 className="w-5 h-5 text-green-400" />
                      <button
                        onClick={() => disableMutation.mutate(target.name)}
                        disabled={disableMutation.isPending}
                        className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-sm transition-colors"
                      >
                        Disable
                      </button>
                    </>
                  ) : (
                    <>
                      <XCircle className="w-5 h-5 text-gray-500" />
                      <button
                        onClick={() => enableMutation.mutate(target.name)}
                        disabled={enableMutation.isPending}
                        className="px-3 py-1 bg-orange-500 hover:bg-orange-600 rounded text-sm transition-colors"
                      >
                        Enable
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent Alerts */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold">Recent Alerts</h2>
          <select
            value={selectedSeverity}
            onChange={(e) => setSelectedSeverity(e.target.value)}
            className="bg-gray-700 border border-gray-600 rounded px-3 py-1 text-sm"
          >
            <option value="low">All Alerts</option>
            <option value="medium">Medium+</option>
            <option value="high">High+</option>
            <option value="critical">Critical Only</option>
          </select>
        </div>
        {alertsLoading ? (
          <div className="text-center text-gray-400 py-12">Loading alerts...</div>
        ) : alerts.length === 0 ? (
          <div className="text-center text-gray-400 py-12">
            <AlertCircle className="w-12 h-12 mx-auto mb-3 text-gray-600" />
            <p>No alerts to display.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {alerts.map((alert) => (
              <div
                key={alert.id}
                className={`border rounded-lg p-4 ${getSeverityColor(alert.severity)} border-current/20`}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <AlertTriangle className="w-4 h-4" />
                      <span className="font-semibold">{alert.target_name}</span>
                      <span className="text-xs opacity-75">
                        {formatDistanceToNow(new Date(alert.timestamp), { addSuffix: true })}
                      </span>
                    </div>
                    <p className="text-sm mb-2">{alert.summary}</p>
                    {alert.details && (
                      <p className="text-xs opacity-75">{alert.details}</p>
                    )}
                  </div>
                  {alert.acknowledged ? (
                    <span className="text-xs bg-green-500/20 text-green-400 px-2 py-1 rounded">
                      Acknowledged
                    </span>
                  ) : (
                    <button
                      className="text-xs bg-gray-700 hover:bg-gray-600 px-3 py-1 rounded transition-colors"
                    >
                      Acknowledge
                    </button>
                  )}
                </div>
                {alert.anomalies && alert.anomalies.length > 0 && (
                  <div className="text-xs mt-2 space-y-1">
                    {alert.anomalies.slice(0, 3).map((anomaly, idx) => (
                      <div key={idx} className="opacity-75">
                        {new Date(anomaly.timestamp).toLocaleTimeString()}: {anomaly.value.toFixed(2)}
                        (expected: {anomaly.expected.toFixed(2)}, deviation: {(anomaly.deviation * 100).toFixed(1)}%)
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
