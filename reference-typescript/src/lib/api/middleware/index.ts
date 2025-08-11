import { NextRequest } from 'next/server';
import { withAuth } from './auth';
import { withErrorHandler } from './error-handler';
import { withRateLimit, generalRateLimiter, syncRateLimiter } from './rate-limit';

type Handler = (request: NextRequest, context?: any) => Promise<Response>;

export function createApiHandler(
  handler: Handler,
  options: {
    auth?: boolean;
    rateLimit?: boolean;
    customRateLimiter?: (request: NextRequest) => void;
  } = {}
): Handler {
  const { auth = true, rateLimit = true, customRateLimiter } = options;
  
  let wrappedHandler = handler;
  
  if (rateLimit) {
    wrappedHandler = withRateLimit(wrappedHandler, customRateLimiter || generalRateLimiter);
  }
  
  if (auth) {
    wrappedHandler = withAuth(wrappedHandler);
  }
  
  return withErrorHandler(wrappedHandler);
}

export { withAuth } from './auth';
export { withErrorHandler } from './error-handler';
export { withRateLimit, generalRateLimiter, syncRateLimiter } from './rate-limit';
export { validateRequestBody, validateQueryParams } from './validation';