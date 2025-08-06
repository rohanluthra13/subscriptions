import { NextRequest } from 'next/server';
import { z } from 'zod';
import { createApiHandler, validateRequestBody, syncRateLimiter } from '@/lib/api/middleware';
import { successResponse } from '@/lib/api/utils/response';
import { SyncOrchestrator } from '@/services/processing/sync-orchestrator';
import { DatabaseService } from '@/lib/db/service';
import { SubscriptionDetector } from '@/services/llm/subscription-detector';
import { jobProgressEmitter } from '@/lib/api/utils/sse';
import { ApiError, ErrorCode } from '@/lib/api/types/errors';
import type { ManualSyncRequest } from '@/lib/api/types/requests';
import type { ManualSyncResponse } from '@/lib/api/types/responses';

const manualSyncSchema = z.object({
  connection_id: z.string().optional(),
});

export const POST = createApiHandler(
  async (request: NextRequest) => {
    const body = await validateRequestBody<ManualSyncRequest>(
      request,
      manualSyncSchema
    );
    
    const database = new DatabaseService();
    const subscriptionDetector = new SubscriptionDetector();
    const syncOrchestrator = new SyncOrchestrator(database, subscriptionDetector);
    
    // Get connection (use default for single-user MVP)
    const connection = body.connection_id
      ? await database.getConnectionById(body.connection_id)
      : await database.getActiveConnection('1'); // Hardcoded user ID for MVP
    
    if (!connection) {
      throw new ApiError(
        ErrorCode.CONNECTION_NOT_FOUND,
        'No active Gmail connection found',
        404
      );
    }
    
    // Check if sync is already in progress
    const syncInProgress = await syncOrchestrator.isSyncInProgress(connection.id);
    if (syncInProgress) {
      throw new ApiError(
        ErrorCode.SYNC_IN_PROGRESS,
        'A sync is already in progress for this connection',
        409
      );
    }
    
    // Start manual sync in background
    processManualSyncInBackground(connection, syncOrchestrator);
    
    const response: ManualSyncResponse = {
      job_id: 'temp-job-id', // Will be replaced by actual job ID
      status: 'started',
      message: 'Manual sync started - checking for new emails since last sync'
    };
    
    return successResponse(response, 'Manual sync initiated');
  },
  { 
    auth: true, 
    rateLimit: true, 
    customRateLimiter: syncRateLimiter 
  }
);

async function processManualSyncInBackground(
  connection: any,
  syncOrchestrator: SyncOrchestrator
) {
  try {
    const result = await syncOrchestrator.processManualRefresh(connection);
    
    // Emit completion event
    jobProgressEmitter.emit(`complete:${result.jobId}`, {
      jobId: result.jobId,
      stats: result.stats,
      processingTimeMs: result.processingTimeMs,
      message: `Sync completed. Found ${result.stats.subscriptionsFound} new subscriptions.`
    });
  } catch (error) {
    console.error('Manual sync failed:', error);
    
    // Emit error event
    jobProgressEmitter.emit(`error:temp-job-id`, {
      error: error instanceof Error ? error.message : 'Unknown error',
      message: 'Manual sync failed'
    });
  }
}