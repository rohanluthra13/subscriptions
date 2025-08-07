'use client';

import useSWR from 'swr';

const fetcher = async (url: string) => {
  const response = await fetch(url, {
    headers: {
      'X-API-Key': process.env.NEXT_PUBLIC_API_KEY || 'your-secure-api-key-123'
    }
  });
  const data = await response.json();
  console.log('Fetcher received data:', data);
  return data;
};

export function useConnection() {
  const { data, error, isLoading, mutate } = useSWR('/api/connections/status', fetcher);
  
  console.log('useConnection data:', data);
  
  return {
    connection: data?.data?.connection || null,
    isConnected: !!data?.data?.connection?.is_active,
    isLoading,
    error,
    refresh: mutate,
  };
}