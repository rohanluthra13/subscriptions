import { NextRequest } from 'next/server';
import { z } from 'zod';
import { createApiHandler, validateRequestBody } from '@/lib/api/middleware';
import { successResponse } from '@/lib/api/utils/response';
import { generateAuthUrl, generateState } from '@/lib/auth/google-oauth';
import { ApiError, ErrorCode } from '@/lib/api/types/errors';
import type { ConnectGmailRequest } from '@/lib/api/types/requests';
import type { ConnectGmailResponse } from '@/lib/api/types/responses';

// In-memory store for OAuth state (for MVP)
// In production, use Redis or database
const stateStore = new Map<string, { timestamp: number; redirectUri?: string }>();

// Clean up expired states every 5 minutes
setInterval(() => {
  const now = Date.now();
  stateStore.forEach((data, state) => {
    if (now - data.timestamp > 10 * 60 * 1000) { // 10 minutes expiry
      stateStore.delete(state);
    }
  });
}, 5 * 60 * 1000);

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
  
  // Store state with timestamp
  stateStore.set(state, {
    timestamp: Date.now(),
    redirectUri: body.redirect_uri,
  });
  
  // Generate authorization URL
  const authUrl = generateAuthUrl(state);
  
  const response: ConnectGmailResponse = {
    auth_url: authUrl,
    state: state,
  };
  
  return successResponse(response, 'Gmail authorization URL generated');
});