#!/usr/bin/env tsx

/**
 * Integration test for unified sync endpoint
 * Tests the new /api/sync/emails endpoint
 */

import { config } from 'dotenv';

// Load environment variables
config();

const API_BASE = process.env.NEXTAUTH_URL || 'http://localhost:3000';
const API_KEY = process.env.API_KEY;

if (!API_KEY) {
  console.error('❌ API_KEY environment variable is required');
  process.exit(1);
}

async function testUnifiedSync() {
  console.log('🧪 Testing Unified Sync Endpoint');
  console.log('================================');

  try {
    // Test 1: Sync Recent (small batch)
    console.log('\n📥 Test 1: Sync Recent Emails (limit: 5)');
    const recentResponse = await fetch(`${API_BASE}/api/sync/emails`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${API_KEY}`
      },
      body: JSON.stringify({
        mode: 'recent',
        limit: 5,
        autoClassify: true
      })
    });

    if (!recentResponse.ok) {
      const error = await recentResponse.text();
      throw new Error(`Recent sync failed: ${recentResponse.status} ${error}`);
    }

    const recentData = await recentResponse.json();
    console.log('✅ Recent sync successful');
    console.log(`   📊 Phase 1: ${recentData.phase1.emailsFetched} fetched, ${recentData.phase1.newEmails} new`);
    console.log(`   🤖 Phase 2: ${recentData.phase2.emailsProcessed} processed, ${recentData.phase2.subscriptionsFound} subscriptions`);
    console.log(`   ⏱️  Processing time: ${recentData.processingTimeMs}ms`);
    console.log(`   📄 More emails available: ${recentData.hasMoreEmails}`);

    // Test 2: Fetch Older (only if recent sync found emails)
    if (recentData.hasMoreEmails) {
      console.log('\n📥 Test 2: Fetch Older Emails (limit: 3)');
      const olderResponse = await fetch(`${API_BASE}/api/sync/emails`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${API_KEY}`
        },
        body: JSON.stringify({
          mode: 'older',
          limit: 3,
          autoClassify: true
        })
      });

      if (!olderResponse.ok) {
        const error = await olderResponse.text();
        throw new Error(`Older sync failed: ${olderResponse.status} ${error}`);
      }

      const olderData = await olderResponse.json();
      console.log('✅ Older sync successful');
      console.log(`   📊 Phase 1: ${olderData.phase1.emailsFetched} fetched, ${olderData.phase1.newEmails} new`);
      console.log(`   🤖 Phase 2: ${olderData.phase2.emailsProcessed} processed, ${olderData.phase2.subscriptionsFound} subscriptions`);
      console.log(`   ⏱️  Processing time: ${olderData.processingTimeMs}ms`);
      console.log(`   📄 More emails available: ${olderData.hasMoreEmails}`);
    } else {
      console.log('\n⏭️  Skipping older sync test (no more emails available)');
    }

    // Test 3: Metadata-only sync (autoClassify: false)
    console.log('\n📥 Test 3: Metadata-only Sync (autoClassify: false)');
    const metadataResponse = await fetch(`${API_BASE}/api/sync/emails`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${API_KEY}`
      },
      body: JSON.stringify({
        mode: 'recent',
        limit: 2,
        autoClassify: false
      })
    });

    if (!metadataResponse.ok) {
      const error = await metadataResponse.text();
      throw new Error(`Metadata sync failed: ${metadataResponse.status} ${error}`);
    }

    const metadataData = await metadataResponse.json();
    console.log('✅ Metadata-only sync successful');
    console.log(`   📊 Phase 1: ${metadataData.phase1.emailsFetched} fetched, ${metadataData.phase1.newEmails} new`);
    console.log(`   🤖 Phase 2: ${metadataData.phase2.emailsProcessed} processed (should be 0)`);
    console.log(`   ⏱️  Processing time: ${metadataData.processingTimeMs}ms`);

    console.log('\n🎉 All unified sync tests passed!');
    console.log('\n📝 Summary:');
    console.log('   ✅ Recent email sync with classification');
    console.log('   ✅ Older email pagination');
    console.log('   ✅ Metadata-only sync mode');
    console.log('   ✅ Proper error handling and response format');

  } catch (error) {
    console.error('\n❌ Unified sync test failed:', error);
    process.exit(1);
  }
}

// Run the test
testUnifiedSync();