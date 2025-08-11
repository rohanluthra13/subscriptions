import { NextRequest } from 'next/server';
import { ApiError, ErrorCode } from '../types/errors';

interface RateLimitEntry {
  count: number;
  resetTime: number;
}

// In-memory store for rate limiting
const rateLimitStore = new Map<string, RateLimitEntry>();

// Clean up expired entries every 5 minutes
setInterval(() => {
  const now = Date.now();
  rateLimitStore.forEach((entry, key) => {
    if (entry.resetTime < now) {
      rateLimitStore.delete(key);
    }
  });
}, 5 * 60 * 1000);

export interface RateLimitConfig {
  windowMs: number;
  max: number;
  keyGenerator?: (request: NextRequest) => string;
}

const defaultKeyGenerator = (request: NextRequest): string => {
  const apiKey = request.headers.get('x-api-key') || 
                 request.nextUrl.searchParams.get('api_key') ||
                 'anonymous';
  return `${apiKey}:${request.nextUrl.pathname}`;
};

export function createRateLimiter(config: RateLimitConfig) {
  const { windowMs, max, keyGenerator = defaultKeyGenerator } = config;

  return function rateLimiter(request: NextRequest): void {
    const key = keyGenerator(request);
    const now = Date.now();
    const resetTime = now + windowMs;

    let entry = rateLimitStore.get(key);

    if (!entry || entry.resetTime < now) {
      entry = { count: 1, resetTime };
      rateLimitStore.set(key, entry);
      return;
    }

    entry.count++;

    if (entry.count > max) {
      const retryAfter = Math.ceil((entry.resetTime - now) / 1000);
      throw new ApiError(
        ErrorCode.RATE_LIMIT_EXCEEDED,
        `Rate limit exceeded. Try again in ${retryAfter} seconds`,
        429,
        { retryAfter }
      );
    }
  };
}

// Pre-configured rate limiters
export const generalRateLimiter = createRateLimiter({
  windowMs: 60 * 1000, // 1 minute
  max: 100, // 100 requests per minute
});

export const syncRateLimiter = createRateLimiter({
  windowMs: 60 * 1000, // 1 minute
  max: 10, // 10 sync requests per minute
});

export function withRateLimit(
  handler: (request: NextRequest, context?: any) => Promise<Response>,
  rateLimiter: (request: NextRequest) => void = generalRateLimiter
): (request: NextRequest, context?: any) => Promise<Response> {
  return async (request: NextRequest, context?: any) => {
    rateLimiter(request);
    return await handler(request, context);
  };
}