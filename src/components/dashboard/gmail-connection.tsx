'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useConnection } from '@/hooks/use-connection';

export function GmailConnection() {
  const { connection, isConnected, isLoading, error } = useConnection();
  const [isConnecting, setIsConnecting] = useState(false);

  const handleConnect = async () => {
    setIsConnecting(true);
    try {
      const response = await fetch('/api/connections/gmail', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await response.json();
      
      if (data.auth_url) {
        window.location.href = data.auth_url;
      }
    } catch (error) {
      console.error('Failed to initiate Gmail connection:', error);
    } finally {
      setIsConnecting(false);
    }
  };

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/4 mb-2"></div>
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="p-6 border-red-200">
        <h3 className="text-lg font-semibold text-red-900 mb-2">Connection Error</h3>
        <p className="text-red-600 text-sm">
          Failed to check Gmail connection status. Please try again.
        </p>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Gmail Connection</h3>
          {isConnected ? (
            <div className="flex items-center space-x-2 mt-1">
              <Badge variant="outline" className="text-green-600 border-green-200">
                Connected
              </Badge>
              <span className="text-sm text-gray-600">
                {connection?.email}
              </span>
            </div>
          ) : (
            <p className="text-sm text-gray-600 mt-1">
              Connect your Gmail account to start tracking subscriptions
            </p>
          )}
        </div>
        
        {!isConnected && (
          <Button 
            onClick={handleConnect} 
            disabled={isConnecting}
            className="bg-blue-600 hover:bg-blue-700"
          >
            {isConnecting ? 'Connecting...' : 'Connect Gmail'}
          </Button>
        )}
      </div>
      
      {isConnected && connection?.last_sync_at && (
        <div className="mt-4 text-xs text-gray-500">
          Last synced: {new Date(connection.last_sync_at).toLocaleString()}
        </div>
      )}
    </Card>
  );
}