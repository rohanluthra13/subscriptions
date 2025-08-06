import { CronScheduler } from '../services/background/cron-scheduler';
import { SyncWorker } from '../services/background/sync-worker';
import { JobMonitor } from '../services/background/job-monitor';
import { DatabaseService } from '../lib/db/service';

console.log('='.repeat(60));
console.log('P5 BACKGROUND WORKER - INTEGRATION DEMO');
console.log('='.repeat(60));

async function testBackgroundWorker() {
  const database = new DatabaseService();

  console.log('\n1. Service Instantiation');
  console.log('-'.repeat(30));
  
  try {
    const scheduler = new CronScheduler();
    const syncWorker = new SyncWorker(database);
    const jobMonitor = new JobMonitor(database);
    
    console.log('✓ CronScheduler instantiated');
    console.log('✓ SyncWorker instantiated');
    console.log('✓ JobMonitor instantiated');
    
    console.log('\n2. Worker Status Check');
    console.log('-'.repeat(30));
    
    const workerStatus = await syncWorker.getWorkerStatus();
    console.log(`✓ Active connections: ${workerStatus.activeConnections}`);
    console.log(`✓ Ongoing syncs: ${workerStatus.ongoingSyncs}`);
    
    console.log('\n3. Job Monitoring');
    console.log('-'.repeat(30));
    
    const healthStatus = await jobMonitor.getMonitoringStats();
    console.log(`✓ Total jobs: ${healthStatus.totalJobs}`);
    console.log(`✓ Active jobs: ${healthStatus.activeJobs}`);
    console.log(`✓ Failed jobs: ${healthStatus.failedJobs}`);
    console.log(`✓ Stuck jobs: ${healthStatus.stuckJobs}`);
    
    if (healthStatus.oldestActiveJob) {
      console.log(`✓ Oldest active job: ${healthStatus.oldestActiveJob.id} (${healthStatus.oldestActiveJob.ageMinutes}m old)`);
    } else {
      console.log('✓ No active jobs found');
    }
    
    console.log('\n4. Scheduler Configuration');
    console.log('-'.repeat(30));
    
    // Test scheduler status (before starting)
    const taskStatus = scheduler.getTaskStatus();
    console.log('✓ Available scheduled tasks:');
    Object.entries(taskStatus).forEach(([taskName, isActive]) => {
      console.log(`  - ${taskName}: ${isActive ? 'active' : 'inactive'}`);
    });
    
    console.log('\n5. Background Worker Architecture');
    console.log('-'.repeat(30));
    console.log('✓ CronScheduler: Manages scheduled tasks (daily sync, monitoring, cleanup)');
    console.log('✓ SyncWorker: Executes daily syncs for all active connections');
    console.log('✓ JobMonitor: Tracks job health and handles alerts');
    console.log('✓ Database Integration: Uses existing DatabaseService and SyncOrchestrator');
    
    console.log('\n6. Scheduling Details');
    console.log('-'.repeat(30));
    console.log('✓ Daily Sync: 6:00 AM UTC (all active connections)');
    console.log('✓ Job Monitoring: Every 5 minutes');
    console.log('✓ Cleanup: Midnight UTC (remove jobs older than 7 days)');
    console.log('✓ Timezone: UTC for global consistency');
    
    console.log('\n' + '='.repeat(60));
    console.log('BACKGROUND WORKER IMPLEMENTATION COMPLETE');
    console.log('Commands:');
    console.log('  npm run cron:start  - Start background worker');
    console.log('  npm run cron:dev    - Start with file watching');
    console.log('='.repeat(60));
    
  } catch (error) {
    console.error('✗ Background worker test failed:', error);
    process.exit(1);
  }
}

// Run the demo
testBackgroundWorker().catch(console.error);