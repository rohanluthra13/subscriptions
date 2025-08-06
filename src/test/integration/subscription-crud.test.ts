/**
 * Subscription CRUD Integration Test
 * 
 * Tests subscription management operations:
 * - Create, Read, Update, Delete
 * - Search and filtering
 * - Export functionality
 */

import { setupTestContext, teardownTestContext, TestReporter } from './setup';

async function main() {
  console.log('🧪 Subscription CRUD Integration Test');
  console.log('======================================\n');
  
  const reporter = new TestReporter();
  const context = await setupTestContext();
  
  let testSubscriptionId: string | undefined;
  
  try {
    // Test 1: Create a subscription
    await reporter.runTest('Create new subscription', async () => {
      const subscription = await context.database.createSubscription({
        userId: context.testUserId,
        vendorName: 'Test Service',
        vendorEmail: 'billing@testservice.com',
        amount: '9.99',
        currency: 'USD',
        billingCycle: 'monthly',
        status: 'active',
        category: 'Software',
        nextBillingDate: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
        detectedFromEmail: 'test-email-id',
        confidence: 0.95,
      });
      
      if (!subscription || !subscription.id) {
        throw new Error('Failed to create subscription');
      }
      
      testSubscriptionId = subscription.id;
      
      console.log(`   Created subscription: ${subscription.id}`);
      console.log(`   Vendor: ${subscription.vendorName}`);
      console.log(`   Amount: ${subscription.currency}${subscription.amount}`);
    });
    
    // Test 2: Read subscription by ID
    await reporter.runTest('Read subscription by ID', async () => {
      if (!testSubscriptionId) {
        throw new Error('No test subscription ID');
      }
      
      const subscription = await context.database.getSubscriptionById(testSubscriptionId);
      
      if (!subscription) {
        throw new Error('Subscription not found');
      }
      
      if (subscription.vendorName !== 'Test Service') {
        throw new Error('Retrieved wrong subscription');
      }
      
      console.log(`   Retrieved subscription: ${subscription.vendorName}`);
      console.log(`   Status: ${subscription.status}`);
    });
    
    // Test 3: Update subscription
    await reporter.runTest('Update subscription details', async () => {
      if (!testSubscriptionId) {
        throw new Error('No test subscription ID');
      }
      
      const updated = await context.database.updateSubscription(testSubscriptionId, {
        amount: '19.99',
        status: 'paused',
        notes: 'Updated via test',
      });
      
      if (!updated) {
        throw new Error('Update failed');
      }
      
      if (updated.amount !== '19.99' || updated.status !== 'paused') {
        throw new Error('Update not applied correctly');
      }
      
      console.log(`   Updated amount: ${updated.amount}`);
      console.log(`   Updated status: ${updated.status}`);
      console.log(`   Notes: ${updated.notes}`);
    });
    
    // Test 4: List subscriptions with filters
    await reporter.runTest('List subscriptions with filters', async () => {
      // Create a few more test subscriptions
      await context.database.createSubscription({
        userId: context.testUserId,
        vendorName: 'Spotify',
        vendorEmail: 'spotify@billing.com',
        amount: '9.99',
        currency: 'USD',
        billingCycle: 'monthly',
        status: 'active',
        category: 'Entertainment',
      });
      
      await context.database.createSubscription({
        userId: context.testUserId,
        vendorName: 'Netflix',
        vendorEmail: 'netflix@billing.com',
        amount: '15.99',
        currency: 'USD',
        billingCycle: 'monthly',
        status: 'inactive',
        category: 'Entertainment',
      });
      
      // Test different filters
      const allSubs = await context.database.getSubscriptions({
        userId: context.testUserId,
      });
      
      const activeSubs = await context.database.getSubscriptions({
        userId: context.testUserId,
        status: 'active',
      });
      
      const entertainmentSubs = await context.database.getSubscriptions({
        userId: context.testUserId,
        category: 'Entertainment',
      });
      
      console.log(`   Total subscriptions: ${allSubs.total}`);
      console.log(`   Active subscriptions: ${activeSubs.total}`);
      console.log(`   Entertainment subscriptions: ${entertainmentSubs.total}`);
      
      if (allSubs.total < activeSubs.total) {
        throw new Error('Filter logic error: active > total');
      }
    });
    
    // Test 5: Search functionality
    await reporter.runTest('Search subscriptions by name', async () => {
      const results = await context.database.getSubscriptions({
        userId: context.testUserId,
        search: 'Netflix',
      });
      
      if (results.total === 0) {
        throw new Error('Search found no results');
      }
      
      const netflix = results.items.find(s => s.vendorName === 'Netflix');
      if (!netflix) {
        throw new Error('Search did not return expected subscription');
      }
      
      console.log(`   Search for "Netflix" found ${results.total} result(s)`);
    });
    
    // Test 6: Sort functionality
    await reporter.runTest('Sort subscriptions', async () => {
      const byAmount = await context.database.getSubscriptions({
        userId: context.testUserId,
        sort: 'amount',
        order: 'desc',
      });
      
      if (byAmount.items.length > 1) {
        const amounts = byAmount.items.map(s => parseFloat(s.amount || '0'));
        const isSorted = amounts.every((val, i, arr) => i === 0 || arr[i - 1] >= val);
        
        if (!isSorted) {
          throw new Error('Subscriptions not sorted correctly by amount');
        }
      }
      
      console.log(`   Sorted by amount (desc): ${byAmount.items.map(s => s.amount).join(', ')}`);
    });
    
    // Test 7: Pagination
    await reporter.runTest('Pagination works correctly', async () => {
      const page1 = await context.database.getSubscriptions({
        userId: context.testUserId,
        limit: 2,
        offset: 0,
      });
      
      const page2 = await context.database.getSubscriptions({
        userId: context.testUserId,
        limit: 2,
        offset: 2,
      });
      
      console.log(`   Page 1: ${page1.items.length} items`);
      console.log(`   Page 2: ${page2.items.length} items`);
      
      // Check no overlap
      const page1Ids = page1.items.map(s => s.id);
      const page2Ids = page2.items.map(s => s.id);
      const overlap = page1Ids.some(id => page2Ids.includes(id));
      
      if (overlap) {
        throw new Error('Pagination has overlapping results');
      }
    });
    
    // Test 8: Subscription statistics
    await reporter.runTest('Calculate subscription statistics', async () => {
      const stats = await context.database.getSubscriptionStats(context.testUserId);
      
      console.log(`   Total active: ${stats.totalActive}`);
      console.log(`   Monthly cost: $${stats.monthlyTotal.toFixed(2)}`);
      console.log(`   Yearly cost: $${stats.yearlyTotal.toFixed(2)}`);
      console.log(`   By category: ${JSON.stringify(stats.byCategory)}`);
      
      if (stats.monthlyTotal < 0 || stats.yearlyTotal < 0) {
        throw new Error('Invalid statistics calculated');
      }
    });
    
    // Test 9: Export functionality
    await reporter.runTest('Export subscriptions to CSV', async () => {
      const subscriptions = await context.database.getSubscriptions({
        userId: context.testUserId,
      });
      
      // Simulate CSV export
      const csvHeaders = ['Vendor', 'Amount', 'Currency', 'Cycle', 'Status', 'Category'];
      const csvRows = subscriptions.items.map(s => [
        s.vendorName,
        s.amount,
        s.currency,
        s.billingCycle,
        s.status,
        s.category || '',
      ]);
      
      const csvContent = [
        csvHeaders.join(','),
        ...csvRows.map(row => row.join(',')),
      ].join('\n');
      
      if (!csvContent.includes('Vendor')) {
        throw new Error('CSV export failed');
      }
      
      console.log(`   Exported ${subscriptions.items.length} subscriptions`);
      console.log(`   CSV size: ${csvContent.length} bytes`);
    });
    
    // Test 10: Delete subscription
    await reporter.runTest('Delete subscription', async () => {
      if (!testSubscriptionId) {
        throw new Error('No test subscription ID');
      }
      
      const deleted = await context.database.deleteSubscription(testSubscriptionId);
      
      if (!deleted) {
        throw new Error('Delete failed');
      }
      
      // Verify deletion
      const checkDeleted = await context.database.getSubscriptionById(testSubscriptionId);
      
      if (checkDeleted) {
        throw new Error('Subscription not actually deleted');
      }
      
      console.log(`   Deleted subscription: ${testSubscriptionId}`);
    });
    
    // Test 11: Bulk operations
    await reporter.runTest('Bulk update subscriptions', async () => {
      const activeSubs = await context.database.getSubscriptions({
        userId: context.testUserId,
        status: 'active',
      });
      
      if (activeSubs.items.length === 0) {
        console.log('   No active subscriptions to bulk update');
        return;
      }
      
      // Simulate bulk pause
      const updates = await Promise.all(
        activeSubs.items.slice(0, 2).map(sub =>
          context.database.updateSubscription(sub.id, { status: 'paused' })
        )
      );
      
      const allPaused = updates.every(sub => sub?.status === 'paused');
      
      if (!allPaused) {
        throw new Error('Bulk update failed');
      }
      
      console.log(`   Bulk updated ${updates.length} subscriptions`);
    });
    
    // Test 12: Duplicate detection
    await reporter.runTest('Duplicate subscription detection', async () => {
      // Try to create a duplicate
      await context.database.createSubscription({
        userId: context.testUserId,
        vendorName: 'Duplicate Test',
        vendorEmail: 'duplicate@test.com',
        amount: '5.99',
        currency: 'USD',
        billingCycle: 'monthly',
        status: 'active',
      });
      
      // Check for duplicate
      const duplicate = await context.database.findDuplicateSubscription(
        context.testUserId,
        'duplicate@test.com',
        '5.99'
      );
      
      if (!duplicate) {
        throw new Error('Duplicate detection failed');
      }
      
      console.log(`   Duplicate detection working`);
      console.log(`   Found duplicate: ${duplicate.vendorName}`);
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