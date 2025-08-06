import { JobQueue } from '../batch/job-queue';
import type { SyncJob } from '../../lib/db/schema';
import type { JobMetrics } from '../batch/job-types';

export interface ProgressUpdate {
  jobId: string;
  processed: number;
  total: number;
  subscriptionsFound: number;
  errors: number;
  percentage: number;
  estimatedTimeRemaining: number;
  currentOperation?: string;
}

export interface ProgressCallback {
  (update: ProgressUpdate): void;
}

export class ProgressTracker {
  private callbacks = new Map<string, ProgressCallback[]>();
  private jobMetrics = new Map<string, JobMetrics>();
  private startTimes = new Map<string, number>();

  constructor(private jobQueue: JobQueue) {}

  subscribe(jobId: string, callback: ProgressCallback): () => void {
    if (!this.callbacks.has(jobId)) {
      this.callbacks.set(jobId, []);
    }
    
    this.callbacks.get(jobId)!.push(callback);
    
    return () => {
      const callbacks = this.callbacks.get(jobId);
      if (callbacks) {
        const index = callbacks.indexOf(callback);
        if (index > -1) {
          callbacks.splice(index, 1);
        }
        if (callbacks.length === 0) {
          this.callbacks.delete(jobId);
        }
      }
    };
  }

  async startTracking(jobId: string, totalEmails: number): Promise<void> {
    this.startTimes.set(jobId, Date.now());
    
    await this.jobQueue.updateJobProgress(jobId, {
      totalEmails,
      processedEmails: 0,
      subscriptionsFound: 0,
      errorsCount: 0
    });

    this.emitProgress(jobId, {
      jobId,
      processed: 0,
      total: totalEmails,
      subscriptionsFound: 0,
      errors: 0,
      percentage: 0,
      estimatedTimeRemaining: 0,
      currentOperation: 'Starting email processing...'
    });
  }

  async updateProgress(
    jobId: string,
    progress: {
      processed: number;
      subscriptionsFound: number;
      errors: number;
      currentOperation?: string;
    }
  ): Promise<void> {
    const job = await this.jobQueue.getJob(jobId);
    if (!job) return;

    await this.jobQueue.updateJobProgress(jobId, {
      processedEmails: progress.processed,
      subscriptionsFound: progress.subscriptionsFound,
      errorsCount: progress.errors
    });

    const totalEmails = job.totalEmails || 0;
    const percentage = totalEmails > 0 ? 
      Math.round((progress.processed / totalEmails) * 100) : 0;

    const estimatedTimeRemaining = this.calculateEstimatedTime(
      jobId,
      progress.processed,
      totalEmails
    );

    this.emitProgress(jobId, {
      jobId,
      processed: progress.processed,
      total: totalEmails,
      subscriptionsFound: progress.subscriptionsFound,
      errors: progress.errors,
      percentage,
      estimatedTimeRemaining: estimatedTimeRemaining || 0,
      currentOperation: progress.currentOperation
    });
  }

  async completeTracking(jobId: string, finalStats: {
    processed: number;
    subscriptionsFound: number;
    errors: number;
  }): Promise<void> {
    const job = await this.jobQueue.getJob(jobId);
    if (!job) return;

    this.emitProgress(jobId, {
      jobId,
      processed: finalStats.processed,
      total: job.totalEmails || 0,
      subscriptionsFound: finalStats.subscriptionsFound,
      errors: finalStats.errors,
      percentage: 100,
      estimatedTimeRemaining: 0,
      currentOperation: 'Sync completed'
    });

    this.cleanup(jobId);
  }

  async getProgress(jobId: string): Promise<ProgressUpdate | null> {
    const job = await this.jobQueue.getJob(jobId);
    if (!job) return null;

    const totalEmails = job.totalEmails || 0;
    const processedEmails = job.processedEmails || 0;
    const percentage = totalEmails > 0 ? 
      Math.round((processedEmails / totalEmails) * 100) : 0;

    const estimatedTimeRemaining = this.calculateEstimatedTime(
      jobId,
      processedEmails,
      totalEmails
    );

    return {
      jobId,
      processed: processedEmails,
      total: totalEmails,
      subscriptionsFound: job.subscriptionsFound || 0,
      errors: job.errorsCount || 0,
      percentage,
      estimatedTimeRemaining: estimatedTimeRemaining || 0,
      currentOperation: this.getOperationForStatus(job.status || 'pending')
    };
  }

  private emitProgress(jobId: string, update: ProgressUpdate): void {
    const callbacks = this.callbacks.get(jobId);
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(update);
        } catch (error) {
          console.error(`Progress callback error for job ${jobId}:`, error);
        }
      });
    }
  }

  private calculateEstimatedTime(
    jobId: string,
    processed: number,
    total: number
  ): number | undefined {
    const startTime = this.startTimes.get(jobId);
    if (!startTime || processed === 0) return undefined;

    const elapsedMs = Date.now() - startTime;
    const emailsPerMs = processed / elapsedMs;
    const remainingEmails = total - processed;
    
    const result = Math.round(remainingEmails / emailsPerMs);
    return isNaN(result) ? 0 : result;
  }

  private getOperationForStatus(status: string): string {
    switch (status) {
      case 'pending': return 'Queued for processing...';
      case 'running': return 'Processing emails...';
      case 'completed': return 'Sync completed';
      case 'failed': return 'Sync failed';
      case 'cancelled': return 'Sync cancelled';
      default: return 'Unknown status';
    }
  }

  private cleanup(jobId: string): void {
    this.callbacks.delete(jobId);
    this.startTimes.delete(jobId);
    this.jobMetrics.delete(jobId);
  }

  getAllActiveProgress(): Promise<ProgressUpdate[]> {
    return Promise.all(
      Array.from(this.callbacks.keys()).map(jobId => this.getProgress(jobId))
    ).then(results => results.filter(Boolean) as ProgressUpdate[]);
  }
}