export enum ErrorCode {
  UNAUTHORIZED = 'UNAUTHORIZED',
  GMAIL_API_ERROR = 'GMAIL_API_ERROR',
  SYNC_IN_PROGRESS = 'SYNC_IN_PROGRESS',
  SUBSCRIPTION_NOT_FOUND = 'SUBSCRIPTION_NOT_FOUND',
  VALIDATION_ERROR = 'VALIDATION_ERROR',
  RATE_LIMIT_EXCEEDED = 'RATE_LIMIT_EXCEEDED',
  INTERNAL_ERROR = 'INTERNAL_ERROR',
  CONNECTION_NOT_FOUND = 'CONNECTION_NOT_FOUND',
  INVALID_EXPORT_FORMAT = 'INVALID_EXPORT_FORMAT',
}

export class ApiError extends Error {
  constructor(
    public code: ErrorCode,
    public message: string,
    public statusCode: number = 400,
    public details?: Record<string, any>
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export interface ErrorResponse {
  error: {
    code: string;
    message: string;
    details?: Record<string, any>;
  };
}