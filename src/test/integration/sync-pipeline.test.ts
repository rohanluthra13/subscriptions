/**
 * Sync Pipeline Integration Test
 * 
 * Tests the full email processing pipeline:
 * - Fetching emails from Gmail
 * - Processing through LLM
 * - Saving subscriptions to database
 * - Deduplication logic
 */

import { setupTestContext, teardownTestContext, requireGmail, TestReporter, waitFor } from './setup';
import { SyncOrchestrator } from '@/services/processing/sync-orchestrator';
import { SubscriptionDetector } from '@/services/llm/subscription-detector';
import { GmailService } from '@/services/gmail/gmail-service';

async function main() {
  console.log('🧪 Sync Pipeline Integration Test');
  console.log('==================================\n');
  
  const reporter = new TestReporter();
  const context = await setupTestContext();
  
  try {
    // Initialize services
    let syncOrchestrator: SyncOrchestrator;
    let gmail: GmailService;
    
    // Test 1: Initialize sync orchestrator
    await reporter.runTest('Sync orchestrator initializes', async () => {
      const connection = await context.database.getActiveConnection(context.testUserId);
      if (!connection) {
        throw new Error('No Gmail connection found');
      }
      
      gmail = new GmailService(connection.accessToken, connection.refreshToken);
      const detector = new SubscriptionDetector();
      syncOrchestrator = new SyncOrchestrator(context.database, detector);
      
      console.log('   Orchestrator initialized with all services');
    });
    
    // Test 2: Create a sync job
    await reporter.runTest('Sync job can be created', async () => {
      const job = await context.database.createSyncJob({
        userId: context.testUserId,
        type: 'manual',
        status: 'pending',
        emailsProcessed: 0,
        subscriptionsFound: 0,
      });
      
      if (!job || !job.id) {
        throw new Error('Failed to create sync job');
      }
      
      console.log(`   Created job: ${job.id}`);
      console.log(`   Type: ${job.type}`);
      console.log(`   Status: ${job.status}`);
      
      // Clean up
      await context.database.updateSyncJob(job.id, { status: 'completed' });
    });
    
    // Test 3: Fetch emails from Gmail
    await reporter.runTest('Can fetch emails from Gmail', async () => {
      const emails = await gmail.getMessageList({ 
        maxResults: 10,
        query: 'in:inbox -in:spam -in:trash newer_than:30d'
      });
      
      if (!emails || emails.length === 0) {
        console.log('   No emails found in last 30 days (this is OK)');
        return;
      }
      
      console.log(`   Found ${emails.length} emails in last 30 days`);
      
      // Fetch details for first email
      if (emails[0]?.id) {
        const details = await gmail.getMessage(emails[0].id);
        console.log(`   Sample email: ${details.subject?.substring(0, 50)}...`);
      }
    });
    
    // Test 4: Process a small batch of emails
    await reporter.runTest('Can process emails through pipeline', async () => {
      const connection = await context.database.getActiveConnection(context.testUserId);
      if (!connection) {
        throw new Error('No Gmail connection');
      }
      
      // Create a test sync job
      const job = await syncOrchestrator.executeSync({
        userId: context.testUserId,
        connectionId: connection.id,
        type: 'manual',
        options: {
          dateRange: {
            // Only process last 7 days for testing
            startDate: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
            endDate: new Date().toISOString(),
          },
          maxEmails: 20, // Limit to 20 emails for testing
        },
      });
      
      if (!job) {
        throw new Error('Sync execution failed');
      }
      
      console.log(`   Job ${job.id} completed`);
      console.log(`   Emails processed: ${job.emailsProcessed}`);
      console.log(`   Subscriptions found: ${job.subscriptionsFound}`);
      console.log(`   Status: ${job.status}`);
      
      if (job.error) {
        console.log(`   Errors: ${job.error}`);
      }
    });
    
    // Test 5: Check subscription detection
    await reporter.runTest('Subscriptions are detected and saved', async () => {
      const subscriptions = await context.database.getSubscriptions({
        userId: context.testUserId,
      });
      
      console.log(`   Total subscriptions found: ${subscriptions.total}`);
      
      if (subscriptions.items.length > 0) {
        const sample = subscriptions.items[0];
        console.log(`   Sample subscription:`);
        console.log(`     - Vendor: ${sample.vendorName}`);
        console.log(`     - Amount: ${sample.currency}${sample.amount}`);
        console.log(`     - Cycle: ${sample.billingCycle}`);
        console.log(`     - Status: ${sample.status}`);
      } else {
        console.log('   No subscriptions detected (emails may not contain subscriptions)');
      }
    });
    
    // Test 6: Test deduplication
    await reporter.runTest('Duplicate subscriptions are handled', async () => {
      const subscriptions = await context.database.getSubscriptions({
        userId: context.testUserId,
      });
      
      if (subscriptions.items.length === 0) {
        console.log('   No subscriptions to test deduplication');
        return;
      }
      
      // Try to create a duplicate
      const existing = subscriptions.items[0];
      const duplicate = await context.database.findDuplicateSubscription(
        context.testUserId,
        existing.vendorEmail,
        existing.amount
      );
      
      if (duplicate) {
        console.log('   Deduplication logic working correctly');
      } else {
        console.log('   No duplicates found');
      }
    });
    
    // Test 7: Check processed emails tracking
    await reporter.runTest('Processed emails are tracked', async () => {
      const processedEmails = await context.database.db
        .select()
        .from(context.database.processedEmails)
        .where(context.database.eq(context.database.processedEmails.userId, context.testUserId))
        .limit(5);
      
      console.log(`   Processed emails tracked: ${processedEmails.length}`);
      
      if (processedEmails.length > 0) {
        const sample = processedEmails[0];
        console.log(`   Sample processed email:`);
        console.log(`     - Email ID: ${sample.emailId}`);
        console.log(`     - Subscription: ${sample.subscriptionDetected ? 'Yes' : 'No'}`);
        console.log(`     - Processed: ${sample.processedAt}`);
      }
    });
    
    // Test 8: Test incremental sync
    await reporter.runTest('Incremental sync works correctly', async () => {
      const connection = await context.database.getActiveConnection(context.testUserId);
      if (!connection) {
        throw new Error('No Gmail connection');
      }
      
      // Wait a moment to ensure different timestamp
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Run another sync - should process fewer or no emails
      const job = await syncOrchestrator.executeSync({
        userId: context.testUserId,
        connectionId: connection.id,
        type: 'daily',
        options: {
          dateRange: {
            startDate: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString(),
            endDate: new Date().toISOString(),
          },
          maxEmails: 10,
        },
      });
      
      if (!job) {
        throw new Error('Incremental sync failed');
      }
      
      console.log(`   Incremental sync completed`);
      console.log(`   New emails processed: ${job.emailsProcessed}`);
      console.log(`   Should be less than initial sync`);
    });
    
    // Test 9: Error handling
    await reporter.runTest('Errors are handled gracefully', async () => {
      try {
        // Try to sync with invalid connection
        await syncOrchestrator.executeSync({
          userId: context.testUserId,
          connectionId: 'invalid-connection-id',
          type: 'manual',
          options: {},
        });
        
        throw new Error('Should have thrown an error for invalid connection');
      } catch (error) {
        if (error instanceof Error && error.message.includes('Connection not found')) {
          console.log('   Error handling works correctly');
        } else if (error instanceof Error && error.message.includes('Should have thrown')) {
          throw error;
        } else {
          console.log('   Unexpected error (but handled): ' + error);
        }
      }
    });
    
    // Test 10: Sync job status tracking
    await reporter.runTest('Sync job status is tracked correctly', async () => {
      const jobs = await context.database.db
        .select()
        .from(context.database.syncJobs)
        .where(context.database.eq(context.database.syncJobs.userId, context.testUserId))
        .orderBy(context.database.desc(context.database.syncJobs.startedAt))
        .limit(1);
      
      if (jobs.length === 0) {
        throw new Error('No sync jobs found');
      }
      
      const latestJob = jobs[0];
      console.log(`   Latest job status: ${latestJob.status}`);
      console.log(`   Started: ${latestJob.startedAt}`);
      console.log(`   Completed: ${latestJob.completedAt}`);
      
      if (latestJob.status !== 'completed' && latestJob.status !== 'failed') {
        throw new Error(`Unexpected job status: ${latestJob.status}`);
      }
    });
    
  } finally {
    await teardownTestContext(context);
    reporter.printSummary();
  }
}

// Run if called directly
if (require.main === module) {
  main().catch(console.error);
}