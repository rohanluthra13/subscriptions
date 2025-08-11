import { NextRequest } from 'next/server';
import { z } from 'zod';
import { ApiError, ErrorCode } from '../types/errors';

export async function validateRequestBody<T>(
  request: NextRequest,
  schema: z.ZodSchema<T>
): Promise<T> {
  try {
    const body = await request.json();
    return schema.parse(body);
  } catch (error) {
    if (error instanceof z.ZodError) {
      throw new ApiError(
        ErrorCode.VALIDATION_ERROR,
        'Invalid request body',
        400,
        { errors: error.errors }
      );
    }
    throw new ApiError(
      ErrorCode.VALIDATION_ERROR,
      'Invalid JSON in request body',
      400
    );
  }
}

export function validateQueryParams<T>(
  request: NextRequest,
  schema: z.ZodSchema<T>
): T {
  const params = Object.fromEntries(request.nextUrl.searchParams.entries());
  
  try {
    return schema.parse(params);
  } catch (error) {
    if (error instanceof z.ZodError) {
      throw new ApiError(
        ErrorCode.VALIDATION_ERROR,
        'Invalid query parameters',
        400,
        { errors: error.errors }
      );
    }
    throw error;
  }
}

// Common validation schemas
export const paginationSchema = z.object({
  limit: z.coerce.number().min(1).max(100).default(20),
  offset: z.coerce.number().min(0).default(0),
});

export const sortSchema = z.object({
  sort: z.enum(['amount', 'date', 'name']).optional(),
  order: z.enum(['asc', 'desc']).default('desc'),
});