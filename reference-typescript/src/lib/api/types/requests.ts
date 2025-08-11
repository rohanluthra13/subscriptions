export interface ConnectGmailRequest {
  redirect_uri?: string;
}

export interface ManualSyncRequest {
  connection_id?: string;
}

export interface UpdateSubscriptionRequest {
  status?: 'active' | 'inactive' | 'paused' | 'unknown';
  amount?: number;
  billing_cycle?: 'monthly' | 'yearly' | 'weekly' | 'one-time';
  next_billing_date?: string;
  user_notes?: string;
  user_verified?: boolean;
}

export interface ListSubscriptionsQuery {
  status?: 'active' | 'inactive' | 'paused' | 'unknown';
  category?: string;
  sort?: 'amount' | 'date' | 'name';
  order?: 'asc' | 'desc';
  search?: string;
  limit?: number;
  offset?: number;
}

export interface ExportQuery {
  format: 'csv' | 'json';
  status?: string;
  category?: string;
  date_range?: string;
}