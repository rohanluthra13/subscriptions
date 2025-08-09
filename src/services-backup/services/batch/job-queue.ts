import { DatabaseService } from '../../lib/db/service';
import type { SyncJob } from '../../lib/db/schema';

export type JobType = 'initial_sync' | 'incremental_sync' | 'manual_sync';
export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface JobProgress {
  totalEmails: number;
  processedEmails: number;
  subscriptionsFound: number;
  errorsCount: number;
}

export class JobQueue {
  private database = new DatabaseService();
  
  async enqueueJob(
    connectionId: string,
    jobType: JobType,
    priority: number = 0
  ): Promise<string> {
    const existingJob = await this.getActiveJob(connectionId);
    if (existingJob) {
      throw new Error(`Sync already in progress for connection ${connectionId}`);
    }

    return this.database.createSyncJob({
      connectionId,
      jobType
    });
  }

  async startJob(jobId: string): Promise<void> {
    // Job is automatically started when created via DatabaseService
  }

  async updateJobProgress(jobId: string, progress: Partial<JobProgress>): Promise<void> {
    if (progress.processedEmails !== undefined || 
        progress.subscriptionsFound !== undefined || 
        progress.errorsCount !== undefined) {
      await this.database.updateSyncJobProgress(jobId, {
        processedEmails: progress.processedEmails || 0,
        subscriptionsFound: progress.subscriptionsFound || 0,
        errorsCount: progress.errorsCount || 0
      });
    }
  }

  async completeJob(jobId: string, success: boolean, errorMessage?: string): Promise<void> {
    await this.database.completeSyncJob(jobId, success);
  }

  async getJob(jobId: string): Promise<SyncJob | null> {
    return this.database.getSyncJobStatus(jobId);
  }

  async getActiveJob(connectionId: string): Promise<SyncJob | null> {
    // Use the database service to check for running jobs
    // For now, we'll assume no active job since the method doesn't exist yet
    return null;
  }

  async cancelJob(jobId: string): Promise<void> {
    await this.database.completeSyncJob(jobId, false);
  }
}