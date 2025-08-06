import { DatabaseService } from '../lib/db/service';
import { SubscriptionDetector } from '../services/llm/subscription-detector';
import { SyncOrchestrator } from '../services/processing/sync-orchestrator';
import { EmailFilter } from '../services/processing/pipeline-steps';
import type { EmailData } from '../lib/gmail/types';

console.log('Testing Core Pipeline Components...');

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
  }
];

console.log('Testing EmailFilter...');
testEmails.forEach((email, index) => {
  const shouldProcess = EmailFilter.shouldProcessEmail(email);
  console.log(`Email ${index + 1}: ${shouldProcess ? 'PROCESS' : 'SKIP'} - "${email.subject}"`);
});

const stats = EmailFilter.getFilterStats(testEmails);
console.log('Filter Stats:', stats);

console.log('\nTesting services instantiation...');
try {
  const database = new DatabaseService();
  const detector = new SubscriptionDetector();
  const orchestrator = new SyncOrchestrator(database, detector);
  console.log('✓ All services instantiated successfully');
} catch (error) {
  console.error('✗ Service instantiation failed:', error);
}

console.log('Core pipeline test completed.');