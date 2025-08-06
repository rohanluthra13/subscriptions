import { NextRequest } from 'next/server';
import { z } from 'zod';
import { createApiHandler, validateQueryParams } from '@/lib/api/middleware';
import { successResponse } from '@/lib/api/utils/response';
import { DatabaseService } from '@/lib/db/service';
import type { ListSubscriptionsQuery } from '@/lib/api/types/requests';
import type { ListSubscriptionsResponse } from '@/lib/api/types/responses';

const listSubscriptionsSchema = z.object({
  status: z.enum(['active', 'inactive', 'paused', 'unknown']).optional(),
  category: z.string().optional(),
  sort: z.enum(['amount', 'date', 'name']).default('date'),
  order: z.enum(['asc', 'desc']).default('desc'),
  search: z.string().optional(),
  limit: z.coerce.number().min(1).max(100).default(20),
  offset: z.coerce.number().min(0).default(0),
});

export const GET = createApiHandler(async (request: NextRequest) => {
  const query = validateQueryParams<ListSubscriptionsQuery>(
    request,
    listSubscriptionsSchema
  );
  
  const database = new DatabaseService();
  
  // Get subscriptions with filters
  const result = await database.getSubscriptions({
    userId: '1', // Hardcoded for single-user MVP
    status: query.status,
    category: query.category,
    search: query.search,
    sort: query.sort || 'date',
    order: query.order || 'desc',
    limit: query.limit || 20,
    offset: query.offset || 0,
  });
  
  // Calculate summary statistics
  const allSubscriptions = await database.getSubscriptions({
    userId: '1',
    status: 'active', // Only active for summary
  });
  
  const summary = {
    total_monthly: allSubscriptions.items
      .filter((s: any) => s.billingCycle === 'monthly')
      .reduce((sum: number, s: any) => sum + (parseFloat(s.amount || '0')), 0),
    total_yearly: allSubscriptions.items
      .filter((s: any) => s.billingCycle === 'yearly')
      .reduce((sum: number, s: any) => sum + (parseFloat(s.amount || '0')), 0),
    active_count: allSubscriptions.total,
  };
  
  const response: ListSubscriptionsResponse = {
    subscriptions: result.items,
    total: result.total,
    summary,
  };
  
  return successResponse(response);
});