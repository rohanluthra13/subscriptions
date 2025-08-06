import { NextRequest } from 'next/server';
import { createApiHandler } from '@/lib/api/middleware';
import { successResponse } from '@/lib/api/utils/response';
import { SyncOrchestrator } from '@/services/processing/sync-orchestrator';
import { DatabaseService } from '@/lib/db/service';
import { SubscriptionDetector } from '@/services/llm/subscription-detector';
import { ApiError, ErrorCode } from '@/lib/api/types/errors';
import type { SyncStatusResponse } from '@/lib/api/types/responses';

export const GET = createApiHandler(async (request: NextRequest) => {
  const database = new DatabaseService();
  const subscriptionDetector = new SubscriptionDetector();
  const syncOrchestrator = new SyncOrchestrator(database, subscriptionDetector);
  
  // Get connection for single-user MVP
  const connection = await database.getActiveConnection('1');
  
  if (!connection) {
    throw new ApiError(
      ErrorCode.CONNECTION_NOT_FOUND,
      'No active Gmail connection found',
      404
    );
  }
  
  // Check if sync is in progress
  const currentJob = await syncOrchestrator.getCurrentSyncJob(connection.id);
  const isSyncing = !!currentJob;
  
  // Calculate next scheduled sync (daily at 6 AM UTC)
  const now = new Date();
  const next6AM = new Date(now);
  next6AM.setUTCHours(6, 0, 0, 0);
  
  // If current time is past 6 AM today, schedule for tomorrow
  if (now.getUTCHours() >= 6) {
    next6AM.setUTCDate(next6AM.getUTCDate() + 1);
  }
  
  const response: SyncStatusResponse = {
    is_syncing: isSyncing,
    ...(currentJob && {
      current_job: {
        job_id: currentJob.id,
        job_type: currentJob.jobType,
        started_at: currentJob.startedAt?.toISOString() || new Date().toISOString(),
      }
    }),
    last_sync_at: connection.lastSyncAt?.toISOString(),
    next_scheduled_sync: next6AM.toISOString(),
  };
  
  return successResponse(response);
});