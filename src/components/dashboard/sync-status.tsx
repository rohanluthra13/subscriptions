'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import useSWR from 'swr';

const fetcher = (url: string) => fetch(url).then(res => res.json());

export function SyncStatus() {
  const [isStartingSync, setIsStartingSync] = useState(false);
  const { data: syncStatus, error, isLoading, mutate } = useSWR('/api/sync/status', fetcher, {
    refreshInterval: 5000, // Poll every 5 seconds
  });

  const handleManualSync = async () => {
    setIsStartingSync(true);
    try {
      const response = await fetch('/api/sync/manual', {
        method: 'POST',
      });
      
      if (response.ok) {
        mutate(); // Refresh sync status
      }
    } catch (error) {
      console.error('Failed to start manual sync:', error);
    } finally {
      setIsStartingSync(false);
    }
  };

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-gray-200 rounded w-1/4"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="p-6 border-red-200">
        <h3 className="text-lg font-semibold text-red-900 mb-2">Sync Error</h3>
        <p className="text-red-600 text-sm">
          Failed to check sync status. Please try again.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Current Status</h3>
          {syncStatus?.is_syncing ? (
            <Badge className="bg-blue-100 text-blue-800">Syncing</Badge>
          ) : (
            <Badge variant="outline">Idle</Badge>
          )}
        </div>
        
        <div className="space-y-4">
          {syncStatus?.current_job && (
            <div className="bg-blue-50 rounded-md p-4">
              <div className="font-medium text-blue-900">
                {syncStatus.current_job.job_type.replace('_', ' ')} in progress
              </div>
              <div className="text-sm text-blue-700">
                Started: {new Date(syncStatus.current_job.started_at).toLocaleString()}
              </div>
            </div>
          )}
          
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-gray-500">Last Sync:</span>
              <div className="font-medium">
                {syncStatus?.last_sync_at 
                  ? new Date(syncStatus.last_sync_at).toLocaleString()
                  : 'Never'
                }
              </div>
            </div>
            <div>
              <span className="text-gray-500">Next Scheduled:</span>
              <div className="font-medium">
                {syncStatus?.next_scheduled_sync 
                  ? new Date(syncStatus.next_scheduled_sync).toLocaleString()
                  : 'Daily at 6 AM UTC'
                }
              </div>
            </div>
          </div>
          
          <div className="flex justify-end">
            <Button
              onClick={handleManualSync}
              disabled={isStartingSync || syncStatus?.is_syncing}
              className="bg-blue-600 hover:bg-blue-700"
            >
              {isStartingSync 
                ? 'Starting...' 
                : syncStatus?.is_syncing 
                ? 'Sync in Progress' 
                : 'Manual Sync'
              }
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}