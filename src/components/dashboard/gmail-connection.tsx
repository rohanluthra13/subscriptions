'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useConnection } from '@/hooks/use-connection';
import { useSearchParams } from 'next/navigation';

export function GmailConnection() {
  const { connection, isConnected, isLoading, error, refresh } = useConnection();
  const [isConnecting, setIsConnecting] = useState(false);
  const searchParams = useSearchParams();
  
  console.log('GmailConnection state:', { connection, isConnected, isLoading, error });
  
  // Check for OAuth success and refresh connection
  useEffect(() => {
    console.log('useEffect triggered, searchParams:', searchParams.toString());
    if (searchParams.get('success') === 'true') {
      console.log('OAuth success detected, refreshing connection...');
      refresh();
    }
  }, [searchParams, refresh]);

  const handleConnect = async () => {
    console.log('Connect button clicked!');
    console.log('API Key being used:', process.env.NEXT_PUBLIC_API_KEY || 'your-secure-api-key-123');
    setIsConnecting(true);
    try {
      console.log('Sending request to /api/connections/gmail...');
      const response = await fetch('/api/connections/gmail', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-API-Key': process.env.NEXT_PUBLIC_API_KEY || 'your-secure-api-key-123'
        },
        body: JSON.stringify({})
      });
      console.log('Response received:', response.status, response.statusText);
      const data = await response.json();
      console.log('Response data:', data);
      
      if (!response.ok) {
        console.error('Gmail connection error:', data);
        console.error('Full error details:', JSON.stringify(data, null, 2));
        throw new Error(data.error?.message || data.message || 'Failed to connect Gmail');
      }
      
      if (data.data?.auth_url) {
        console.log('Redirecting to:', data.data.auth_url);
        window.location.href = data.data.auth_url;
      } else {
        console.error('No auth_url in response:', data);
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
            type="button"
          >
            {isConnecting ? 'Connecting...' : 'Connect Gmail'}
          </Button>
        )}
        {!isConnected && console.log('Button should be rendered, isConnected:', isConnected)}
      </div>
      
      {isConnected && connection?.last_sync_at && (
        <div className="mt-4 text-xs text-gray-500">
          Last synced: {new Date(connection.last_sync_at).toLocaleString()}
        </div>
      )}
    </Card>
  );
}