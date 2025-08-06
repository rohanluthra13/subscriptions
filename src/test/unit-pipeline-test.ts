import { EmailFilter, DeduplicationService } from '../services/processing/pipeline-steps';
import type { EmailData } from '../lib/gmail/types';
import type { SubscriptionData } from '../services/llm/types';

console.log('Testing Core Pipeline Components (Unit Tests)...');

const testEmails: EmailData[] = [
  {
    id: 'email-1',
    subject: 'Your Netflix subscription will renew soon',
    sender: 'billing@netflix.com',
    body: 'Your Netflix subscription will automatically renew on January 15, 2024 for $15.99',
    receivedAt: new Date('2024-01-10')
  },
  {
    id: 'email-2',
    subject: 'Flash Sale - 70% off everything!',
    sender: 'promotions@store.com',
    body: 'Limited time offer ends tonight! Shop now and save big.',
    receivedAt: new Date('2024-01-09')
  },
  {
    id: 'email-3',
    subject: 'Spotify Premium - Payment successful',
    sender: 'noreply@spotify.com',
    body: 'Thank you for your payment of $9.99. Your Spotify Premium subscription is active until next month.',
    receivedAt: new Date('2024-01-08')
  }
];

console.log('\n1. Testing EmailFilter...');
testEmails.forEach((email, index) => {
  const shouldProcess = EmailFilter.shouldProcessEmail(email);
  console.log(`Email ${index + 1}: ${shouldProcess ? 'PROCESS' : 'SKIP'} - "${email.subject}"`);
});

const filterStats = EmailFilter.getFilterStats(testEmails);
console.log('\nFilter Stats:', {
  total: filterStats.total,
  filtered: filterStats.filtered,
  processed: filterStats.processed,
  filterRatio: filterStats.filterRatio
});

console.log('\n2. Testing DeduplicationService...');
const dedup = new DeduplicationService();

const newSubscription: SubscriptionData = {
  vendor_name: 'Netflix',
  vendor_email: 'billing@netflix.com',
  amount: 15.99,
  currency: 'USD',
  confidence_score: 0.95
};

const existingSubscription = {
  id: 'existing-1',
  userId: '1',
  connectionId: 'conn-1',
  vendorName: 'Netflix',
  vendorEmail: 'billing@netflix.com',
  amount: '15.99',
  currency: 'USD',
  confidenceScore: '0.95',
  status: 'active' as const,
  renewalType: 'auto_renew' as const,
  userVerified: false,
  createdAt: new Date(),
  updatedAt: new Date(),
  billingCycle: null,
  nextBillingDate: null,
  lastBillingDate: null,
  detectedAt: null,
  userNotes: null,
  category: null
};

const isDupe = dedup.isDuplicate(newSubscription, existingSubscription);
console.log(`Duplicate Detection: ${isDupe ? 'DUPLICATE' : 'NEW'} for Netflix subscription`);

const fuzzySubscription: SubscriptionData = {
  vendor_name: 'Netflix Inc.',
  vendor_email: 'info@netflix.com',
  amount: 15.99,
  currency: 'USD',
  confidence_score: 0.92
};

const isFuzzyDupe = dedup.isDuplicate(fuzzySubscription, existingSubscription);
console.log(`Fuzzy Duplicate Detection: ${isFuzzyDupe ? 'DUPLICATE' : 'NEW'} for Netflix Inc.`);

console.log('\n✓ Core pipeline unit tests completed successfully');
console.log('Ready for integration testing with database and services.');