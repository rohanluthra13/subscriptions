import { eq, and, desc } from 'drizzle-orm';
import { GmailService } from '../../lib/gmail/service';
import { SubscriptionDetector } from '../llm/subscription-detector';
import { DatabaseService } from '../../lib/db/service';
import { JobQueue } from '../batch/job-queue';
import { ProgressTracker } from './progress-tracker';
import { DeduplicationService, EmailFilter } from './pipeline-steps';
import { syncJobs } from '../../lib/db/schema';
import type { Connection, SyncJob, NewSyncJob, NewSubscription, NewProcessedEmail } from '../../lib/db/schema';
import type { EmailData } from '../../lib/gmail/types';
import type { ProcessingResult } from '../llm/types';
import type { JobType } from '../batch/job-types';

export interface ProcessingStats {
  processed: number;
  subscriptionsFound: number;
  errors: number;
  totalEmails: number;
}

export interface SyncResult {
  jobId: string;
  stats: ProcessingStats;
  processingTimeMs: number;
  errors: string[];
}

export class SyncOrchestrator {
  private deduplicationService = new DeduplicationService();
  private jobQueue = new JobQueue();
  private progressTracker = new ProgressTracker(this.jobQueue);

  constructor(
    private database: DatabaseService,
    private subscriptionDetector: SubscriptionDetector
  ) {}

  async processOnboarding(connection: Connection): Promise<SyncResult> {
    return this.executeSync(connection, 'initial_sync', async (gmail) => {
      return gmail.getHistoricalEmails({ months: 6 });
    });
  }

  async processDailySync(connection: Connection): Promise<SyncResult> {
    return this.executeSync(connection, 'incremental_sync', async (gmail) => {
      return gmail.getEmailsSince(
        connection.lastSyncAt || new Date(Date.now() - 24 * 60 * 60 * 1000)
      );
    });
  }

  async processManualRefresh(connection: Connection): Promise<SyncResult> {
    return this.executeSync(connection, 'manual_sync', async (gmail) => {
      return gmail.getEmailsSince(
        connection.lastSyncAt || new Date(Date.now() - 24 * 60 * 60 * 1000)
      );
    });
  }

  private async executeSync(
    connection: Connection,
    jobType: JobType,
    getEmailIds: (gmail: GmailService) => Promise<string[]>
  ): Promise<SyncResult> {
    const activeJob = await this.jobQueue.getActiveJob(connection.id);
    if (activeJob) {
      throw new Error(`Sync already in progress for connection ${connection.id}`);
    }

    const gmail = new GmailService({
      id: connection.id,
      userId: connection.userId,
      email: connection.email,
      accessToken: connection.accessToken,
      refreshToken: connection.refreshToken,
      tokenExpiry: connection.tokenExpiry,
      historyId: connection.historyId || undefined,
      lastSyncAt: connection.lastSyncAt || undefined,
      isActive: connection.isActive || true
    });
    const startTime = Date.now();
    const errors: string[] = [];
    
    const jobId = await this.jobQueue.enqueueJob(connection.id, jobType);
    await this.jobQueue.startJob(jobId);

    try {
      const emailIds = await getEmailIds(gmail);
      await this.progressTracker.startTracking(jobId, emailIds.length);

      const stats = await this.processEmailBatch(gmail, connection, emailIds, jobId, errors);
      
      await this.jobQueue.completeJob(jobId, true);
      await this.database.updateConnectionLastSync(connection.id);
      await this.progressTracker.completeTracking(jobId, stats);

      return {
        jobId,
        stats,
        processingTimeMs: Date.now() - startTime,
        errors
      };
    } catch (error) {
      await this.jobQueue.completeJob(jobId, false, error instanceof Error ? error.message : 'Unknown error');
      throw error;
    }
  }

  private async processEmailBatch(
    gmail: GmailService,
    connection: Connection,
    emailIds: string[],
    jobId: string,
    errors: string[]
  ): Promise<ProcessingStats> {
    const stats: ProcessingStats = {
      processed: 0,
      subscriptionsFound: 0,
      errors: 0,
      totalEmails: emailIds.length
    };

    for (const emailId of emailIds) {
      try {
        const alreadyProcessed = await this.database.isEmailProcessed(emailId);
        if (alreadyProcessed) {
          stats.processed++;
          await this.updateProgressIfNeeded(jobId, stats);
          continue;
        }

        const email = await gmail.getMessage(emailId);
        
        let subscriptionFound = false;
        let subscriptionId: string | undefined;
        let confidenceScore: number | undefined;

        if (EmailFilter.shouldProcessEmail(email)) {
          const result = await this.subscriptionDetector.detectSubscription(email);
          
          if (result.subscription) {
            const existing = await this.database.findDuplicateSubscription(
              result.subscription.vendor_name,
              result.subscription.vendor_email || email.sender,
              connection.userId
            );

            if (!existing) {
              const subscription = await this.database.saveSubscription({
                connectionId: connection.id,
                vendorName: result.subscription.vendor_name,
                vendorEmail: result.subscription.vendor_email,
                amount: result.subscription.amount?.toString(),
                currency: result.subscription.currency,
                billingCycle: result.subscription.billing_cycle,
                nextBillingDate: result.subscription.next_billing_date?.toISOString().split('T')[0],
                confidenceScore: result.subscription.confidence_score.toString(),
                category: result.subscription.category
              });
              subscriptionId = subscription.id;
              stats.subscriptionsFound++;
              subscriptionFound = true;
            }
            confidenceScore = result.subscription.confidence_score;
          }
        }

        await this.database.logProcessedEmail({
          connectionId: connection.id,
          gmailMessageId: emailId,
          subject: email.subject,
          sender: email.sender,
          receivedAt: email.receivedAt,
          subscriptionFound,
          subscriptionId,
          confidenceScore: confidenceScore?.toString()
        });

        stats.processed++;
        await this.updateProgressIfNeeded(jobId, stats);

      } catch (error) {
        stats.errors++;
        const errorMsg = error instanceof Error ? error.message : 'Unknown error';
        errors.push(`Email ${emailId}: ${errorMsg}`);
        
        try {
          await this.database.logProcessedEmail({
            connectionId: connection.id,
            gmailMessageId: emailId,
            subscriptionFound: false
          });
        } catch (logError) {
          console.error('Failed to log processing error:', logError);
        }

        await this.updateProgressIfNeeded(jobId, stats);
      }
    }

    return stats;
  }

  private async updateProgressIfNeeded(jobId: string, stats: ProcessingStats): Promise<void> {
    if (stats.processed % 10 === 0 || stats.processed === stats.totalEmails) {
      await this.progressTracker.updateProgress(jobId, {
        processed: stats.processed,
        subscriptionsFound: stats.subscriptionsFound,
        errors: stats.errors,
        currentOperation: `Processing email ${stats.processed}/${stats.totalEmails}`
      });
    }
  }

  async isSyncInProgress(connectionId: string): Promise<boolean> {
    return !!(await this.jobQueue.getActiveJob(connectionId));
  }

  async getCurrentSyncJob(connectionId: string): Promise<SyncJob | null> {
    return this.jobQueue.getActiveJob(connectionId);
  }

  async getSyncProgress(jobId: string) {
    return this.progressTracker.getProgress(jobId);
  }

  async getAllActiveProgress() {
    return this.progressTracker.getAllActiveProgress();
  }

  async cancelSync(jobId: string): Promise<void> {
    await this.jobQueue.cancelJob(jobId);
  }
}