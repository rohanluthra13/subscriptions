import { Subscription, SyncJob } from '@/lib/db/schema';

export interface ConnectGmailResponse {
  auth_url: string;
  state: string;
}

export interface CallbackResponse {
  success: boolean;
  connection_id: string;
  email: string;
}

export interface ManualSyncResponse {
  job_id: string;
  status: 'started';
  message: string;
}

export interface SyncJobStatus {
  id: string;
  job_type: 'initial_sync' | 'incremental_sync' | 'manual_sync';
  status: 'running' | 'completed' | 'failed';
  progress: {
    total_emails: number;
    processed_emails: number;
    subscriptions_found: number;
    errors_count: number;
  };
  started_at: string;
  completed_at?: string;
  error_message?: string;
}

export interface SyncStatusResponse {
  is_syncing: boolean;
  current_job?: {
    job_id: string;
    job_type: string;
    started_at: string;
  };
  last_sync_at?: string;
  next_scheduled_sync: string;
}

export interface ListSubscriptionsResponse {
  subscriptions: Subscription[];
  total: number;
  summary: {
    total_monthly: number;
    total_yearly: number;
    active_count: number;
  };
}

export interface SuccessResponse<T = any> {
  data: T;
  message?: string;
}