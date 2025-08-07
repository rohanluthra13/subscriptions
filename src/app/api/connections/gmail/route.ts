import { NextRequest } from 'next/server';
import { z } from 'zod';
import { createApiHandler, validateRequestBody } from '@/lib/api/middleware';
import { successResponse } from '@/lib/api/utils/response';
import { generateAuthUrl, generateState } from '@/lib/auth/google-oauth';
import { ApiError, ErrorCode } from '@/lib/api/types/errors';
import type { ConnectGmailRequest } from '@/lib/api/types/requests';
import type { ConnectGmailResponse } from '@/lib/api/types/responses';

// OAuth state is now managed via cookies for proper CSRF protection

const connectGmailSchema = z.object({
  redirect_uri: z.string().url().optional(),
});

export const POST = createApiHandler(async (request: NextRequest) => {
  const body = await validateRequestBody<ConnectGmailRequest>(
    request,
    connectGmailSchema
  );
  
  // Generate state for CSRF protection
  const state = generateState();
  
  // Generate authorization URL
  const authUrl = generateAuthUrl(state);
  
  const responseData: ConnectGmailResponse = {
    auth_url: authUrl,
    state: state,
  };
  
  // Create response with cookie
  const response = successResponse(responseData, 'Gmail authorization URL generated');
  
  // Set state cookie for CSRF validation
  response.cookies.set('oauth_state', state, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: 60 * 10, // 10 minutes
    path: '/'
  });
  
  return response;
});