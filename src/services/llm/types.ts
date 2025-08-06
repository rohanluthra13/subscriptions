export interface EmailData {
  id: string;
  subject: string;
  sender: string;
  body: string;
  receivedAt: Date;
}

export interface SubscriptionData {
  vendor_name: string;
  vendor_email: string;
  amount?: number;
  currency?: string;
  billing_cycle?: 'monthly' | 'yearly' | 'weekly' | 'one-time';
  next_billing_date?: Date;
  confidence_score: number;
  category?: string;
  status?: 'active' | 'cancelled' | 'paused' | 'unknown';
  renewal_type?: 'auto_renew' | 'manual_renew' | 'cancelled' | 'free_tier' | 'unknown';
}

export interface LLMResponse {
  is_subscription: boolean;
  confidence_score: number;
  vendor_name?: string;
  vendor_email?: string;
  amount?: number;
  currency?: string;
  billing_cycle?: 'monthly' | 'yearly' | 'weekly' | 'one-time';
  next_billing_date?: string;
  reasoning?: string;
}

export interface LLMProvider {
  detectSubscription(email: EmailData): Promise<SubscriptionData | null>;
  estimateTokenUsage(text: string): number;
  getModelName(): string;
}

export interface CostMetrics {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  estimatedCost: number;
}

export interface ProcessingResult {
  subscription: SubscriptionData | null;
  metrics: CostMetrics;
  processingTime: number;
  error?: string;
}