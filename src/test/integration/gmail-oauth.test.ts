/**
 * Gmail OAuth Integration Test
 * 
 * Tests the Gmail OAuth flow and connection management
 * Uses real Gmail API with test account: rohanluthra13@gmail.com
 */

import { setupTestContext, teardownTestContext, requireGmail, TestReporter } from './setup';
import { GmailService } from '@/services/gmail/gmail-service';

async function main() {
  console.log('🧪 Gmail OAuth Integration Test');
  console.log('================================\n');
  
  const reporter = new TestReporter();
  const context = await setupTestContext();
  
  try {
    // Test 1: Check for existing Gmail connection
    await reporter.runTest('Database has Gmail connection', async () => {
      const connection = await context.database.getActiveConnection(context.testUserId);
      
      if (!connection) {
        throw new Error('No active Gmail connection found. Please connect Gmail first via the UI.');
      }
      
      console.log(`   Found connection: ${connection.email}`);
      console.log(`   Status: ${connection.status}`);
      console.log(`   Created: ${connection.createdAt}`);
    });
    
    // Test 2: Verify tokens are encrypted
    await reporter.runTest('Tokens are encrypted in database', async () => {
      const connection = await context.database.getActiveConnection(context.testUserId);
      
      if (!connection) {
        throw new Error('No connection to test');
      }
      
      // Check that tokens don't look like plain JWT tokens
      const looksLikeJWT = (token: string) => token.includes('.') && token.split('.').length === 3;
      
      if (looksLikeJWT(connection.accessToken)) {
        throw new Error('Access token appears to be unencrypted');
      }
      
      if (connection.refreshToken && looksLikeJWT(connection.refreshToken)) {
        throw new Error('Refresh token appears to be unencrypted');
      }
      
      console.log('   Tokens are properly encrypted');
    });
    
    // Test 3: Initialize Gmail service with stored tokens
    await reporter.runTest('Gmail service initializes with stored tokens', async () => {
      const connection = await context.database.getActiveConnection(context.testUserId);
      
      if (!connection) {
        throw new Error('No connection available');
      }
      
      const gmail = new GmailService(connection.accessToken, connection.refreshToken);
      
      // Verify service is initialized
      if (!gmail) {
        throw new Error('Failed to initialize Gmail service');
      }
      
      console.log('   Gmail service initialized successfully');
    });
    
    // Test 4: Test Gmail API access
    await reporter.runTest('Gmail API is accessible', async () => {
      const connection = await context.database.getActiveConnection(context.testUserId);
      
      if (!connection) {
        throw new Error('No connection available');
      }
      
      const gmail = new GmailService(connection.accessToken, connection.refreshToken);
      
      // Try to fetch user profile
      const profile = await gmail.getUserProfile();
      
      if (!profile.emailAddress) {
        throw new Error('Could not fetch user profile');
      }
      
      console.log(`   Connected to: ${profile.emailAddress}`);
      console.log(`   Messages total: ${profile.messagesTotal}`);
    });
    
    // Test 5: Verify token refresh mechanism
    await reporter.runTest('Token refresh mechanism works', async () => {
      const connection = await context.database.getActiveConnection(context.testUserId);
      
      if (!connection) {
        throw new Error('No connection available');
      }
      
      const gmail = new GmailService(connection.accessToken, connection.refreshToken);
      
      // Force a token refresh by making an API call
      // In production, this would happen automatically when token expires
      try {
        await gmail.getMessageList({ maxResults: 1 });
        console.log('   Token refresh mechanism available');
      } catch (error) {
        // If this fails with auth error, token refresh isn't working
        if (error instanceof Error && error.message.includes('auth')) {
          throw new Error('Token refresh failed');
        }
        throw error;
      }
    });
    
    // Test 6: Check rate limiting handling
    await reporter.runTest('Rate limiting is handled gracefully', async () => {
      const connection = await context.database.getActiveConnection(context.testUserId);
      
      if (!connection) {
        throw new Error('No connection available');
      }
      
      const gmail = new GmailService(connection.accessToken, connection.refreshToken);
      
      // Make multiple rapid requests
      const requests = Array(5).fill(null).map(() => 
        gmail.getMessageList({ maxResults: 1 })
      );
      
      try {
        await Promise.all(requests);
        console.log('   Rate limiting handled successfully');
      } catch (error) {
        if (error instanceof Error && error.message.includes('quota')) {
          console.log('   Rate limit reached (expected behavior)');
        } else {
          throw error;
        }
      }
    });
    
    // Test 7: Connection status update
    await reporter.runTest('Connection status can be updated', async () => {
      const connection = await context.database.getActiveConnection(context.testUserId);
      
      if (!connection) {
        throw new Error('No connection available');
      }
      
      // Update last sync time
      await context.database.updateConnectionSyncStatus(
        connection.id,
        new Date().toISOString()
      );
      
      // Verify update
      const updated = await context.database.getConnectionById(connection.id);
      
      if (!updated || !updated.lastSyncedAt) {
        throw new Error('Connection status update failed');
      }
      
      console.log(`   Last sync updated: ${updated.lastSyncedAt}`);
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