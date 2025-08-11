/**
 * Gmail API types and interfaces
 * Defines data structures for email processing
 */

export interface EmailData {
  id: string;
  threadId?: string;
  subject: string;
  sender: string;
  body: string;
  receivedAt: Date;
  labels?: string[];
  snippet?: string;
}

export interface EmailMetadata {
  id: string;
  threadId?: string;
}

export interface GmailConnection {
  id: string;
  userId: string;
  email: string;
  accessToken: string;
  refreshToken: string;
  tokenExpiry: Date;
  historyId?: string;
  lastSyncAt?: Date;
  isActive: boolean;
}

export interface MessageListOptions {
  maxResults?: number;
  pageToken?: string;
  query?: string;
  includeSpamTrash?: boolean;
}

export interface HistoricalEmailOptions {
  months?: number;
  maxResults?: number;
  query?: string;
}

export interface BatchFetchResult {
  successful: EmailData[];
  failed: Array<{
    id: string;
    error: Error;
  }>;
}

export interface GmailApiError extends Error {
  code?: number;
  statusCode?: number;
  errors?: Array<{
    domain: string;
    reason: string;
    message: string;
  }>;
}

export interface SyncProgress {
  total: number;
  processed: number;
  subscriptionsFound: number;
  errors: number;
}

/**
 * Type guard for Gmail API errors
 */
export function isGmailApiError(error: unknown): error is GmailApiError {
  return (
    error instanceof Error &&
    'code' in error &&
    typeof (error as any).code === 'number'
  );
}

/**
 * Check if error is rate limit error
 */
export function isRateLimitError(error: unknown): boolean {
  if (!isGmailApiError(error)) return false;
  return error.code === 429 || error.code === 403;
}

/**
 * Check if error is auth error requiring re-authentication
 */
export function isAuthError(error: unknown): boolean {
  if (!isGmailApiError(error)) return false;
  return error.code === 401;
}