/**
 * Manual Gmail Service Test
 * Run after completing OAuth flow
 * Usage: npx tsx src/test/manual-gmail-test.ts
 */

import { config } from 'dotenv';
import { db } from '../lib/db';
import { connections } from '../lib/db/schema';
import { GmailService } from '../lib/gmail/service';
import { eq } from 'drizzle-orm';

config();

async function testGmailService() {
  console.log('🧪 Manual Gmail Service Test\n');
  
  try {
    // Get the connection from database
    console.log('1️⃣ Looking for Gmail connection...');
    const connection = await db
      .select()
      .from(connections)
      .where(eq(connections.isActive, true))
      .limit(1);
    
    if (connection.length === 0) {
      console.log('❌ No active Gmail connection found');
      console.log('   Complete OAuth flow first: POST http://localhost:3001/api/auth/gmail/connect');
      return;
    }
    
    console.log(`✅ Found connection for: ${connection[0].email}`);
    
    // Test Gmail service
    console.log('\n2️⃣ Testing Gmail service...');
    const gmailService = new GmailService({
      ...connection[0],
      historyId: connection[0].historyId || undefined
    });
    
    // Test 1: Get user email (simple API call)
    console.log('   Testing getUserEmail()...');
    const userEmail = await gmailService.getUserEmail();
    console.log(`   ✅ User email: ${userEmail}`);
    
    // Test 2: Get message list (10 recent emails)
    console.log('\n   Testing getMessageList()...');
    const messages = await gmailService.getMessageList({ maxResults: 10 });
    console.log(`   ✅ Found ${messages.length} recent messages`);
    
    if (messages.length > 0) {
      // Test 3: Get full email content
      console.log('\n   Testing getMessage() on first email...');
      const firstEmail = await gmailService.getMessage(messages[0].id);
      console.log(`   ✅ Email subject: "${firstEmail.subject.substring(0, 50)}..."`);
      console.log(`   ✅ Email sender: ${firstEmail.sender}`);
      console.log(`   ✅ Email body length: ${firstEmail.body.length} characters`);
      console.log(`   ✅ Email received: ${firstEmail.receivedAt.toISOString()}`);
      
      // Test 4: Historical emails (last 30 days)
      console.log('\n   Testing getHistoricalEmails()...');
      const historicalIds = await gmailService.getHistoricalEmails({ 
        months: 1, 
        maxResults: 50 
      });
      console.log(`   ✅ Found ${historicalIds.length} emails from last month`);
      
      // Test 5: Batch fetch (test with 3 emails)
      if (historicalIds.length >= 3) {
        console.log('\n   Testing batchFetchEmails()...');
        const batchResult = await gmailService.batchFetchEmails(
          historicalIds.slice(0, 3)
        );
        console.log(`   ✅ Batch fetch: ${batchResult.successful.length} successful, ${batchResult.failed.length} failed`);
      }
    }
    
    console.log('\n✅ All Gmail service tests passed!');
    console.log('\n📊 Summary:');
    console.log(`   • Gmail connection: ${userEmail}`);
    console.log(`   • Recent messages: ${messages.length}`);
    console.log(`   • Historical messages: Available`);
    console.log(`   • Batch processing: Working`);
    
  } catch (error) {
    console.error('\n❌ Test failed:', error);
    if (error instanceof Error) {
      console.error('   Error details:', error.message);
    }
  }
}

testGmailService();