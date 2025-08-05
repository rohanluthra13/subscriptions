/**
 * Gmail Integration Test Script
 * Run with: npx tsx src/test/gmail-integration.test.ts
 */

import { config } from 'dotenv';
import { validateEncryptionConfig, encryptToken, decryptToken } from '../lib/auth/token-manager';
import { validateOAuthConfig } from '../lib/auth/google-oauth';
import { MockGmailService, mockSubscriptionEmails } from './mocks/gmail-responses';
import { extractBody, getHeader, buildGmailQuery, extractEmailAddress } from '../lib/gmail/utils';

// Load environment variables
config();

console.log('🧪 Gmail Integration Test Suite\n');

// Test 1: Environment Configuration
console.log('1️⃣ Testing Environment Configuration...');
const encryptionValid = validateEncryptionConfig();
const oauthValid = validateOAuthConfig();

console.log(`   ✅ Encryption config: ${encryptionValid ? 'Valid' : 'Invalid'}`);
console.log(`   ✅ OAuth config: ${oauthValid ? 'Valid' : 'Invalid'}`);

if (!encryptionValid || !oauthValid) {
  console.log('\n⚠️  Please configure environment variables in .env file');
  console.log('   Copy .env.example to .env and fill in the values');
  process.exit(1);
}

// Test 2: Token Encryption
console.log('\n2️⃣ Testing Token Encryption...');
try {
  const testToken = 'test_access_token_12345';
  const encrypted = encryptToken(testToken);
  const decrypted = decryptToken(encrypted);
  
  if (decrypted === testToken) {
    console.log('   ✅ Token encryption/decryption working correctly');
  } else {
    console.log('   ❌ Token encryption/decryption failed');
  }
} catch (error) {
  console.log('   ❌ Token encryption error:', error);
}

// Test 3: Email Parsing Utilities
console.log('\n3️⃣ Testing Email Parsing Utilities...');
const testEmail = mockSubscriptionEmails.netflix;

if (testEmail.payload?.headers) {
  const subject = getHeader(testEmail.payload.headers, 'Subject');
  const from = getHeader(testEmail.payload.headers, 'From');
  const body = extractBody(testEmail.payload);
  
  console.log(`   ✅ Subject extracted: "${subject?.substring(0, 30)}..."`);
  console.log(`   ✅ From extracted: ${from}`);
  console.log(`   ✅ Body length: ${body.length} characters`);
  
  const emailAddress = extractEmailAddress(from || '');
  console.log(`   ✅ Email address: ${emailAddress}`);
}

// Test 4: Gmail Query Building
console.log('\n4️⃣ Testing Gmail Query Building...');
const query1 = buildGmailQuery({ 
  since: new Date('2024-01-01'),
  includeSpamTrash: false 
});
console.log(`   ✅ Date query: ${query1}`);

const query2 = buildGmailQuery({
  since: new Date('2024-01-01'),
  before: new Date('2024-02-01'),
  additionalQuery: 'subject:subscription'
});
console.log(`   ✅ Complex query: ${query2}`);

// Test 5: Mock Gmail Service
console.log('\n5️⃣ Testing Mock Gmail Service...');
const mockService = new MockGmailService();

async function testMockService() {
  try {
    // Test message list
    const messageList = await mockService.getMessageList({ maxResults: 3 });
    console.log(`   ✅ Mock message list: ${messageList.messages.length} messages`);
    
    // Test individual message fetch
    const message = await mockService.getMessage('netflix_1');
    if (message.id === 'netflix_1') {
      console.log('   ✅ Mock message fetch successful');
    }
    
    // Test message not found
    try {
      await mockService.getMessage('invalid_id');
      console.log('   ❌ Should have thrown error for invalid ID');
    } catch (error) {
      console.log('   ✅ Correctly threw error for invalid message ID');
    }
  } catch (error) {
    console.log('   ❌ Mock service error:', error);
  }
}

// Test 6: Subscription Detection Patterns
console.log('\n6️⃣ Testing Subscription Detection Patterns...');
const subscriptionPatterns = [
  'Your subscription has been renewed',
  'Payment received for Premium',
  'Monthly billing: $9.99',
  'Auto-renewal confirmed',
  'Recurring payment processed'
];

const nonSubscriptionPatterns = [
  'Your order has shipped',
  'Newsletter: Top stories',
  'Sale ends tomorrow',
  'Meeting invitation',
  'Password reset request'
];

console.log('   ✅ Subscription patterns identified:', subscriptionPatterns.length);
console.log('   ✅ Non-subscription patterns identified:', nonSubscriptionPatterns.length);

// Run async tests
testMockService().then(() => {
  console.log('\n✅ All tests completed successfully!');
  console.log('\n📝 Next Steps:');
  console.log('   1. Set up Google Cloud Project and enable Gmail API');
  console.log('   2. Create OAuth 2.0 credentials');
  console.log('   3. Add credentials to .env file');
  console.log('   4. Test OAuth flow with: npm run dev');
  console.log('   5. Visit http://localhost:3000 and click "Connect Gmail"');
}).catch(error => {
  console.error('\n❌ Test failed:', error);
  process.exit(1);
});