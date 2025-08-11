'use client';

import useSWR from 'swr';
import { useState } from 'react';

interface SubscriptionFilters {
  status?: string;
  category?: string;
  search?: string;
  sort?: 'amount' | 'date' | 'name';
  order?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

const fetcher = (url: string) => fetch(url, {
  headers: {
    'X-API-Key': process.env.NEXT_PUBLIC_API_KEY || 'dev-key-123'
  }
}).then(res => res.json());

export function useSubscriptions(filters: SubscriptionFilters = {}) {
  const params = new URLSearchParams();
  
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined) {
      params.append(key, value.toString());
    }
  });
  
  const url = `/api/subscriptions${params.toString() ? `?${params.toString()}` : ''}`;
  
  const { data, error, isLoading, mutate } = useSWR(url, fetcher);
  
  return {
    subscriptions: data?.data?.subscriptions || [],
    total: data?.data?.total || 0,
    summary: data?.data?.summary || { total_monthly: 0, total_yearly: 0, active_count: 0 },
    isLoading,
    error,
    refresh: mutate,
  };
}

export function useDeleteSubscription() {
  const [isDeleting, setIsDeleting] = useState(false);
  
  const deleteSubscription = async (id: string) => {
    setIsDeleting(true);
    try {
      const response = await fetch(`/api/subscriptions/${id}`, {
        method: 'DELETE',
        headers: {
          'X-API-Key': process.env.NEXT_PUBLIC_API_KEY || 'dev-key-123'
        }
      });
      
      if (!response.ok) {
        throw new Error('Failed to delete subscription');
      }
      
      return true;
    } catch (error) {
      console.error('Delete failed:', error);
      return false;
    } finally {
      setIsDeleting(false);
    }
  };
  
  return { deleteSubscription, isDeleting };
}