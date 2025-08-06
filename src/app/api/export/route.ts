import { NextRequest } from 'next/server';
import { z } from 'zod';
import { createApiHandler, validateQueryParams } from '@/lib/api/middleware';
import { streamResponse } from '@/lib/api/utils/response';
import { createCSVStream, createJSONStream, generateFilename } from '@/lib/api/utils/export';
import { DatabaseService } from '@/lib/db/service';
import { ApiError, ErrorCode } from '@/lib/api/types/errors';
import type { ExportQuery } from '@/lib/api/types/requests';

const exportQuerySchema = z.object({
  format: z.enum(['csv', 'json']),
  status: z.enum(['active', 'inactive', 'paused', 'unknown']).optional(),
  category: z.string().optional(),
  date_range: z.string().optional(), // TODO: Implement date range filtering
});

export const GET = createApiHandler(async (request: NextRequest) => {
  const query = validateQueryParams<ExportQuery>(
    request,
    exportQuerySchema
  );
  
  const database = new DatabaseService();
  
  // Get all subscriptions matching filters
  const result = await database.getSubscriptions({
    userId: '1', // Hardcoded for single-user MVP
    status: query.status,
    category: query.category,
    // No pagination for export - get all matching records
    limit: 10000, // Reasonable max for single user
    offset: 0,
  });
  
  if (result.items.length === 0) {
    throw new ApiError(
      ErrorCode.VALIDATION_ERROR,
      'No subscriptions found matching the specified criteria',
      404
    );
  }
  
  // Generate filename
  const filename = generateFilename(query.format, {
    status: query.status,
    category: query.category,
  });
  
  // Create appropriate stream based on format
  let stream: ReadableStream<Uint8Array>;
  let contentType: string;
  
  if (query.format === 'csv') {
    stream = createCSVStream(result.items);
    contentType = 'text/csv';
  } else {
    stream = createJSONStream(result.items);
    contentType = 'application/json';
  }
  
  return streamResponse(stream, filename, contentType);
});