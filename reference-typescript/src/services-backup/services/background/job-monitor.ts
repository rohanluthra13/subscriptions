import { DatabaseService } from '../../lib/db/service';
import { eq, and, sql, lt } from 'drizzle-orm';
import { syncJobs } from '../../lib/db/schema';

export interface JobHealthStatus {
  totalJobs: number;
  activeJobs: number;
  failedJobs: number;
  stuckJobs: number;
  oldestActiveJob?: {
    id: string;
    startedAt: Date;
    ageMinutes: number;
  };
}

export class JobMonitor {
  constructor(private database: DatabaseService) {}

  async checkJobHealth(): Promise<JobHealthStatus> {
    console.log('Checking job health status...');
    
    const status = await this.getJobHealthStatus();
    
    // Alert on problematic conditions
    if (status.stuckJobs > 0) {
      await this.handleStuckJobs();
    }
    
    if (status.failedJobs > 10) {
      await this.alertHighFailureRate(status.failedJobs);
    }

    if (status.oldestActiveJob && status.oldestActiveJob.ageMinutes > 60) {
      await this.alertLongRunningJob(status.oldestActiveJob);
    }

    return status;
  }

  private async getJobHealthStatus(): Promise<JobHealthStatus> {
    // Get current job counts
    const [totalResult] = await this.database.db.select({
      count: sql<number>`count(*)`
    }).from(syncJobs);

    const [activeResult] = await this.database.db.select({
      count: sql<number>`count(*)`
    }).from(syncJobs)
    .where(eq(syncJobs.status, 'running'));

    const [failedResult] = await this.database.db.select({
      count: sql<number>`count(*)`
    }).from(syncJobs)
    .where(eq(syncJobs.status, 'failed'));

    // Find stuck jobs (running for more than 2 hours)
    const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000);
    const [stuckResult] = await this.database.db.select({
      count: sql<number>`count(*)`
    }).from(syncJobs)
    .where(and(
      eq(syncJobs.status, 'running'),
      lt(syncJobs.startedAt, twoHoursAgo)
    ));

    // Get oldest active job
    const [oldestActive] = await this.database.db.select({
      id: syncJobs.id,
      startedAt: syncJobs.startedAt
    }).from(syncJobs)
    .where(eq(syncJobs.status, 'running'))
    .orderBy(syncJobs.startedAt)
    .limit(1);

    const oldestActiveJob = oldestActive ? {
      id: oldestActive.id,
      startedAt: oldestActive.startedAt!,
      ageMinutes: Math.floor((Date.now() - oldestActive.startedAt!.getTime()) / 60000)
    } : undefined;

    return {
      totalJobs: totalResult.count,
      activeJobs: activeResult.count,
      failedJobs: failedResult.count,
      stuckJobs: stuckResult.count,
      oldestActiveJob
    };
  }

  private async handleStuckJobs(): Promise<void> {
    console.log('Handling stuck jobs...');
    
    const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000);
    
    // Mark stuck jobs as failed
    const result = await this.database.db.update(syncJobs)
      .set({
        status: 'failed',
        completedAt: sql`NOW()`,
        errorMessage: 'Job stuck - exceeded 2 hour timeout'
      })
      .where(and(
        eq(syncJobs.status, 'running'),
        lt(syncJobs.startedAt, twoHoursAgo)
      ))
      .returning({ id: syncJobs.id });

    if (result.length > 0) {
      console.log(`Marked ${result.length} stuck jobs as failed:`, result.map(job => job.id));
      await this.sendAlert('stuck_jobs', `${result.length} jobs were stuck and marked as failed`);
    }
  }

  private async alertHighFailureRate(failedCount: number): Promise<void> {
    console.warn(`High failure rate detected: ${failedCount} failed jobs`);
    await this.sendAlert('high_failure_rate', `${failedCount} failed jobs detected`);
  }

  private async alertLongRunningJob(job: { id: string; ageMinutes: number }): Promise<void> {
    console.warn(`Long running job detected: ${job.id} (${job.ageMinutes} minutes)`);
    await this.sendAlert('long_running_job', `Job ${job.id} has been running for ${job.ageMinutes} minutes`);
  }

  private async sendAlert(type: string, message: string): Promise<void> {
    // In production, this would integrate with:
    // - Email notifications
    // - Slack webhooks
    // - PagerDuty
    // - Error tracking services
    
    console.error(`ALERT [${type.toUpperCase()}]: ${message}`);
    
    // For now, just log to console
    // Future: Implement actual alerting mechanisms
  }

  async getMonitoringStats(): Promise<JobHealthStatus> {
    return this.getJobHealthStatus();
  }

  // Emergency stop all running jobs
  async emergencyStopAllJobs(): Promise<void> {
    console.log('EMERGENCY: Stopping all running jobs...');
    
    const result = await this.database.db.update(syncJobs)
      .set({
        status: 'failed',
        completedAt: sql`NOW()`,
        errorMessage: 'Emergency stop - all jobs cancelled'
      })
      .where(eq(syncJobs.status, 'running'))
      .returning({ id: syncJobs.id });

    console.log(`Emergency stopped ${result.length} jobs:`, result.map(job => job.id));
    await this.sendAlert('emergency_stop', `Emergency stopped ${result.length} running jobs`);
  }
}