import * as cron from 'node-cron';
import { DatabaseService } from '../../lib/db/service';
import { SyncWorker } from './sync-worker';
import { JobMonitor } from './job-monitor';

export class CronScheduler {
  private syncWorker: SyncWorker;
  private jobMonitor: JobMonitor;
  private database: DatabaseService;
  private tasks: Map<string, cron.ScheduledTask> = new Map();

  constructor() {
    this.database = new DatabaseService();
    this.syncWorker = new SyncWorker(this.database);
    this.jobMonitor = new JobMonitor(this.database);
  }

  start(): void {
    console.log('Starting background scheduler...');
    
    // Daily sync at 6 AM UTC
    const dailySyncTask = cron.schedule('0 6 * * *', async () => {
      console.log('Starting daily sync at 6 AM UTC');
      await this.syncWorker.executeDailySyncForAllConnections();
    }, {
      timezone: 'UTC'
    });

    // Job monitoring every 5 minutes
    const monitorTask = cron.schedule('*/5 * * * *', async () => {
      await this.jobMonitor.checkJobHealth();
    }, {
      timezone: 'UTC'
    });

    // Cleanup completed jobs older than 7 days - runs daily at midnight UTC
    const cleanupTask = cron.schedule('0 0 * * *', async () => {
      console.log('Running daily cleanup of old sync jobs');
      await this.database.cleanupOldSyncJobs(7);
    }, {
      timezone: 'UTC'
    });

    this.tasks.set('daily-sync', dailySyncTask);
    this.tasks.set('job-monitor', monitorTask);
    this.tasks.set('cleanup', cleanupTask);

    // Start all tasks
    this.tasks.forEach((task, name) => {
      task.start();
      console.log(`✓ Started ${name} task`);
    });

    console.log('All background tasks started successfully');
  }

  stop(): void {
    console.log('Stopping background scheduler...');
    
    this.tasks.forEach((task, name) => {
      task.stop();
      console.log(`✓ Stopped ${name} task`);
    });

    this.tasks.clear();
    console.log('All background tasks stopped');
  }

  // For testing - trigger daily sync manually
  async triggerDailySync(): Promise<void> {
    console.log('Manually triggering daily sync...');
    await this.syncWorker.executeDailySyncForAllConnections();
  }

  // Get status of all scheduled tasks
  getTaskStatus(): Record<string, boolean> {
    const status: Record<string, boolean> = {};
    
    this.tasks.forEach((task, name) => {
      status[name] = task.getStatus() === 'scheduled';
    });

    return status;
  }
}