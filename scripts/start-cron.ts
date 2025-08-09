#!/usr/bin/env tsx

/**
 * Standalone background worker process for subscription tracker
 * 
 * This script starts the cron scheduler as a separate Node.js process
 * that runs independently from the Next.js web application.
 * 
 * Usage:
 *   npm run cron:start
 *   npm run cron:dev (for development with file watching)
 */

// TODO: Re-enable after Phase 1 complete
// import { CronScheduler } from '../src/services/background/cron-scheduler';
import { env } from '../src/lib/env';

// let scheduler: CronScheduler | null = null;

async function startCronService() {
  console.log('🚀 Starting Subscription Tracker Background Worker');
  console.log('='.repeat(60));
  
  try {
    // Validate environment
    console.log('✓ Environment validation passed');
    console.log(`Database: ${env.DATABASE_URL.split('@')[1] || 'configured'}`);
    console.log(`Log Level: ${env.LOG_LEVEL}`);
    
    // TODO: Re-enable after Phase 1 complete
    console.log('⚠️ Cron scheduler disabled during Phase 1 development');
    return;
    
    console.log('='.repeat(60));
    console.log('🎯 Background worker is running');
    console.log('✓ Daily sync scheduled for 6:00 AM UTC');
    console.log('✓ Job monitoring active (every 5 minutes)');
    console.log('✓ Cleanup scheduled for midnight UTC');
    console.log('');
    console.log('Press Ctrl+C to stop');
    console.log('='.repeat(60));
    
  } catch (error) {
    console.error('❌ Failed to start background worker:', error);
    process.exit(1);
  }
}

// Graceful shutdown handling
function setupGracefulShutdown() {
  const shutdown = (signal: string) => {
    console.log(`\n📡 Received ${signal}, shutting down gracefully...`);
    
    // if (scheduler) {
    //   scheduler.stop();
    //   console.log('✓ Background scheduler stopped');
    // }
    
    console.log('👋 Background worker shutdown complete');
    process.exit(0);
  };

  process.on('SIGINT', () => shutdown('SIGINT'));
  process.on('SIGTERM', () => shutdown('SIGTERM'));
  
  // Handle uncaught errors
  process.on('uncaughtException', (error) => {
    console.error('💥 Uncaught exception:', error);
    // if (scheduler) {
    //   scheduler.stop();
    // }
    process.exit(1);
  });

  process.on('unhandledRejection', (reason, promise) => {
    console.error('💥 Unhandled rejection at:', promise, 'reason:', reason);
    // if (scheduler) {
    //   scheduler.stop();
    // }
    process.exit(1);
  });
}

// Start the service
async function main() {
  setupGracefulShutdown();
  await startCronService();
  
  // Keep the process alive (disabled during Phase 1)
  setInterval(() => {
    console.log('📊 Background worker placeholder active');
  }, 5 * 60 * 1000); // Log health every 5 minutes
}

// Only run if this script is executed directly
if (require.main === module) {
  main().catch((error) => {
    console.error('💥 Fatal error starting background worker:', error);
    process.exit(1);
  });
}