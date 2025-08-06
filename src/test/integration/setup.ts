/**
 * Test Setup and Utilities
 * 
 * Provides common setup for integration tests including:
 * - Database setup/teardown
 * - Gmail authentication
 * - Test data management
 */

import { DatabaseService } from '@/lib/db/service';
import { GmailService } from '@/services/gmail/gmail-service';
import { config } from 'dotenv';
import path from 'path';

// Load test environment variables
config({ path: path.resolve(process.cwd(), '.env.test') });

export interface TestContext {
  database: DatabaseService;
  gmail?: GmailService;
  testUserId: string;
  testEmail: string;
}

/**
 * Initialize test context
 */
export async function setupTestContext(): Promise<TestContext> {
  const database = new DatabaseService();
  const testUserId = '1'; // Single user MVP
  const testEmail = 'rohanluthra13@gmail.com';
  
  // Clear test data
  await cleanupTestData(database, testUserId);
  
  // Set up Gmail if credentials exist
  let gmail: GmailService | undefined;
  if (process.env.GMAIL_CLIENT_ID && process.env.GMAIL_CLIENT_SECRET) {
    try {
      // Check for existing connection
      const connection = await database.getActiveConnection(testUserId);
      if (connection) {
        gmail = new GmailService(connection.accessToken, connection.refreshToken);
      }
    } catch (error) {
      console.log('Gmail setup skipped: No active connection');
    }
  }
  
  return {
    database,
    gmail,
    testUserId,
    testEmail,
  };
}

/**
 * Clean up test data
 */
export async function cleanupTestData(
  database: DatabaseService,
  userId: string
): Promise<void> {
  try {
    // Clear subscriptions
    await database.db
      .delete(database.subscriptions)
      .where(database.eq(database.subscriptions.userId, userId));
    
    // Clear processed emails
    await database.db
      .delete(database.processedEmails)
      .where(database.eq(database.processedEmails.userId, userId));
    
    // Clear sync jobs
    await database.db
      .delete(database.syncJobs)
      .where(database.eq(database.syncJobs.userId, userId));
    
    console.log('Test data cleaned up');
  } catch (error) {
    console.error('Cleanup failed:', error);
  }
}

/**
 * Tear down test context
 */
export async function teardownTestContext(context: TestContext): Promise<void> {
  await cleanupTestData(context.database, context.testUserId);
}

/**
 * Skip test if Gmail is not configured
 */
export function requireGmail(context: TestContext): void {
  if (!context.gmail) {
    console.log('⚠️  Skipping test: Gmail not configured');
    console.log('   Set up Gmail connection or provide test credentials');
    process.exit(0);
  }
}

/**
 * Wait for a condition to be true
 */
export async function waitFor(
  condition: () => Promise<boolean>,
  timeout = 30000,
  interval = 1000
): Promise<void> {
  const start = Date.now();
  
  while (Date.now() - start < timeout) {
    if (await condition()) {
      return;
    }
    await new Promise(resolve => setTimeout(resolve, interval));
  }
  
  throw new Error(`Timeout waiting for condition after ${timeout}ms`);
}

/**
 * Test result reporter
 */
export class TestReporter {
  private tests: Array<{ name: string; passed: boolean; error?: string }> = [];
  
  addTest(name: string, passed: boolean, error?: string): void {
    this.tests.push({ name, passed, error });
    
    const symbol = passed ? '✅' : '❌';
    console.log(`${symbol} ${name}`);
    if (error) {
      console.error(`   ${error}`);
    }
  }
  
  async runTest(name: string, fn: () => Promise<void>): Promise<void> {
    try {
      await fn();
      this.addTest(name, true);
    } catch (error) {
      this.addTest(name, false, error instanceof Error ? error.message : String(error));
    }
  }
  
  printSummary(): void {
    console.log('\n' + '='.repeat(50));
    console.log('Test Summary:');
    console.log('='.repeat(50));
    
    const passed = this.tests.filter(t => t.passed).length;
    const failed = this.tests.filter(t => !t.passed).length;
    
    console.log(`Total: ${this.tests.length}`);
    console.log(`Passed: ${passed} ✅`);
    console.log(`Failed: ${failed} ❌`);
    
    if (failed > 0) {
      console.log('\nFailed tests:');
      this.tests
        .filter(t => !t.passed)
        .forEach(t => console.log(`  - ${t.name}: ${t.error}`));
    }
    
    console.log('='.repeat(50));
    
    // Exit with appropriate code
    process.exit(failed > 0 ? 1 : 0);
  }
}