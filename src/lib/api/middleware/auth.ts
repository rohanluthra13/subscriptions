import { NextRequest } from 'next/server';
import { ApiError, ErrorCode } from '../types/errors';

const API_KEY = process.env.API_KEY || 'dev-key-123';

export function authenticateRequest(request: NextRequest): void {
  const apiKey = request.headers.get('x-api-key') || 
                 request.nextUrl.searchParams.get('api_key');
  
  if (!apiKey || apiKey !== API_KEY) {
    throw new ApiError(
      ErrorCode.UNAUTHORIZED,
      'Invalid or missing API key',
      401
    );
  }
}

export function withAuth(
  handler: (request: NextRequest, context?: any) => Promise<Response>
): (request: NextRequest, context?: any) => Promise<Response> {
  return async (request: NextRequest, context?: any) => {
    try {
      authenticateRequest(request);
      return await handler(request, context);
    } catch (error) {
      if (error instanceof ApiError && error.code === ErrorCode.UNAUTHORIZED) {
        throw error;
      }
      throw error;
    }
  };
}