import { NextRequest } from 'next/server';
import { z } from 'zod';
import { createApiHandler, validateRequestBody } from '@/lib/api/middleware';
import { successResponse, noContentResponse } from '@/lib/api/utils/response';
import { DatabaseService } from '@/lib/db/service';
import { ApiError, ErrorCode } from '@/lib/api/types/errors';
import type { UpdateSubscriptionRequest } from '@/lib/api/types/requests';

interface RouteParams {
  params: {
    id: string;
  };
}

const updateSubscriptionSchema = z.object({
  status: z.enum(['active', 'inactive', 'paused', 'unknown']).optional(),
  amount: z.number().min(0).optional(),
  billing_cycle: z.enum(['monthly', 'yearly', 'weekly', 'one-time']).optional(),
  next_billing_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
  user_notes: z.string().max(500).optional(),
  user_verified: z.boolean().optional(),
});

// GET /api/subscriptions/[id] - Get single subscription
export const GET = createApiHandler(async (
  request: NextRequest,
  { params }: RouteParams
) => {
  const subscriptionId = params.id;
  const database = new DatabaseService();
  
  const subscription = await database.getSubscriptionById(subscriptionId, '1');
  
  if (!subscription) {
    throw new ApiError(
      ErrorCode.SUBSCRIPTION_NOT_FOUND,
      `Subscription with ID ${subscriptionId} not found`,
      404
    );
  }
  
  return successResponse(subscription);
});

// PUT /api/subscriptions/[id] - Update subscription
export const PUT = createApiHandler(async (
  request: NextRequest,
  { params }: RouteParams
) => {
  const subscriptionId = params.id;
  const body = await validateRequestBody<UpdateSubscriptionRequest>(
    request,
    updateSubscriptionSchema
  );
  
  const database = new DatabaseService();
  
  // Check if subscription exists
  const existing = await database.getSubscriptionById(subscriptionId, '1');
  if (!existing) {
    throw new ApiError(
      ErrorCode.SUBSCRIPTION_NOT_FOUND,
      `Subscription with ID ${subscriptionId} not found`,
      404
    );
  }
  
  // Update subscription
  const updated = await database.updateSubscription(subscriptionId, {
    status: body.status,
    amount: body.amount?.toString(),
    billingCycle: body.billing_cycle,
    nextBillingDate: body.next_billing_date,
    userNotes: body.user_notes,
    userVerified: body.user_verified,
    updatedAt: new Date(),
  });
  
  return successResponse(updated, 'Subscription updated successfully');
});

// DELETE /api/subscriptions/[id] - Delete subscription
export const DELETE = createApiHandler(async (
  request: NextRequest,
  { params }: RouteParams
) => {
  const subscriptionId = params.id;
  const database = new DatabaseService();
  
  // Check if subscription exists
  const existing = await database.getSubscriptionById(subscriptionId, '1');
  if (!existing) {
    throw new ApiError(
      ErrorCode.SUBSCRIPTION_NOT_FOUND,
      `Subscription with ID ${subscriptionId} not found`,
      404
    );
  }
  
  // Delete subscription
  await database.deleteSubscription(subscriptionId);
  
  return noContentResponse();
});