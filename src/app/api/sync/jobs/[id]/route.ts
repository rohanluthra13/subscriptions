import { NextRequest } from 'next/server';
import { createApiHandler } from '@/lib/api/middleware';
import { successResponse, sseResponse } from '@/lib/api/utils/response';
import { createJobProgressStream } from '@/lib/api/utils/sse';
import { SyncOrchestrator } from '@/services/processing/sync-orchestrator';
import { DatabaseService } from '@/lib/db/service';
import { SubscriptionDetector } from '@/services/llm/subscription-detector';
import { ApiError, ErrorCode } from '@/lib/api/types/errors';
import type { SyncJobStatus } from '@/lib/api/types/responses';

interface RouteParams {
  params: {
    id: string;
  };
}

export const GET = createApiHandler(async (
  request: NextRequest,
  { params }: RouteParams
) => {
  const jobId = params.id;
  const isSSE = request.headers.get('accept') === 'text/event-stream';
  
  const database = new DatabaseService();
  const subscriptionDetector = new SubscriptionDetector();
  const syncOrchestrator = new SyncOrchestrator(database, subscriptionDetector);
  
  // Get job from database
  const job = await database.getSyncJob(jobId);
  
  if (!job) {
    throw new ApiError(
      ErrorCode.SUBSCRIPTION_NOT_FOUND,
      `Sync job with ID ${jobId} not found`,
      404
    );
  }
  
  // If SSE requested, return progress stream
  if (isSSE) {
    const stream = createJobProgressStream(jobId);
    return sseResponse(stream);
  }
  
  // Otherwise return current job status
  const response: SyncJobStatus = {
    id: job.id,
    job_type: job.jobType as 'initial_sync' | 'incremental_sync' | 'manual_sync',
    status: job.status as 'running' | 'completed' | 'failed',
    progress: {
      total_emails: job.totalEmails || 0,
      processed_emails: job.processedEmails || 0,
      subscriptions_found: job.subscriptionsFound || 0,
      errors_count: job.errorsCount || 0,
    },
    started_at: job.startedAt?.toISOString() || new Date().toISOString(),
    ...(job.completedAt && { completed_at: job.completedAt.toISOString() }),
    ...(job.errorMessage && { error_message: job.errorMessage }),
  };
  
  return successResponse(response);
});