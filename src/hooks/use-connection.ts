'use client';

import useSWR from 'swr';

const fetcher = (url: string) => fetch(url).then(res => res.json());

export function useConnection() {
  const { data, error, isLoading, mutate } = useSWR('/api/connections/status', fetcher);
  
  return {
    connection: data?.connection || null,
    isConnected: !!data?.connection?.is_active,
    isLoading,
    error,
    refresh: mutate,
  };
}