import { NextRequest } from 'next/server';
import { ApiError, ErrorCode } from '../types/errors';

export function authenticateRequest(request: NextRequest): void {
  // Use computed property access to avoid build-time inlining of env values
  const configuredApiKey = ((process as any).env['API_KEY'] || (process as any).env['NEXT_PUBLIC_API_KEY'] || 'dev-key-123').trim();
  const providedHeaderUpper = request.headers.get('X-API-Key');
  const providedHeaderLower = request.headers.get('x-api-key');
  const providedQuery = request.nextUrl.searchParams.get('api_key');
  const apiKey = (providedHeaderUpper || providedHeaderLower || providedQuery || '').trim();
  // Debug logs to trace auth issues
  try {
    console.log('[auth] URL:', request.nextUrl.pathname);
    console.log('[auth] providedHeaderUpper:', providedHeaderUpper, '| providedHeaderLower:', providedHeaderLower, '| providedQuery:', providedQuery);
    console.log('[auth] lengths -> provided:', apiKey.length, 'configured:', configuredApiKey.length);
    console.log('[auth] equality ->', apiKey === configuredApiKey);
  } catch {}
  
  if (!apiKey || apiKey !== configuredApiKey) {
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