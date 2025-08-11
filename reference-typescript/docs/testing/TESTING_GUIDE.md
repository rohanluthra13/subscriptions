# Testing Guide

## Overview

This project uses integration tests with real Gmail API to ensure end-to-end functionality works correctly.

## Test Structure

```
src/test/integration/
├── setup.ts                 # Test utilities and helpers
├── gmail-oauth.test.ts      # Gmail connection tests
├── sync-pipeline.test.ts    # Email sync tests
├── subscription-crud.test.ts # Subscription management tests
└── run-all.ts              # Run all tests
```

## Running Tests

### Prerequisites

1. **Gmail Connection**: The test account (`rohanluthra13@gmail.com`) must be connected via the UI first:
   ```bash
   # Start the app
   docker-compose up
   
   # Go to http://localhost:3000/dashboard
   # Click "Connect Gmail" and complete OAuth
   ```

2. **Environment Variables**: Create `.env.test` or use `.env.local`:
   ```env
   DATABASE_URL=postgresql://subscription_user:subscription_pass@localhost:5432/subscription_tracker
   GMAIL_CLIENT_ID=your_client_id
   GMAIL_CLIENT_SECRET=your_client_secret
   OPENAI_API_KEY=your_api_key
   ENCRYPTION_KEY=your_32_char_encryption_key_here!!
   ```

### Run Individual Tests

```bash
# Gmail OAuth test
tsx src/test/integration/gmail-oauth.test.ts

# Sync Pipeline test
tsx src/test/integration/sync-pipeline.test.ts

# Subscription CRUD test
tsx src/test/integration/subscription-crud.test.ts
```

### Run All Tests

```bash
# Using npm script
npm run test:integration

# Or directly
tsx src/test/integration/run-all.ts
```

## What Each Test Covers

### Gmail OAuth Test (`gmail-oauth.test.ts`)
- ✅ Database has Gmail connection
- ✅ Tokens are encrypted
- ✅ Gmail service initializes
- ✅ Gmail API is accessible
- ✅ Token refresh works
- ✅ Rate limiting handled
- ✅ Connection status updates

### Sync Pipeline Test (`sync-pipeline.test.ts`)
- ✅ Sync orchestrator initializes
- ✅ Sync jobs created
- ✅ Emails fetched from Gmail
- ✅ Emails processed through pipeline
- ✅ Subscriptions detected
- ✅ Deduplication works
- ✅ Processed emails tracked
- ✅ Incremental sync works
- ✅ Error handling
- ✅ Job status tracking

### Subscription CRUD Test (`subscription-crud.test.ts`)
- ✅ Create subscriptions
- ✅ Read by ID
- ✅ Update subscriptions
- ✅ List with filters
- ✅ Search functionality
- ✅ Sorting works
- ✅ Pagination works
- ✅ Statistics calculation
- ✅ Export to CSV
- ✅ Delete subscriptions
- ✅ Bulk operations
- ✅ Duplicate detection

## Test Data

Tests use real data from `rohanluthra13@gmail.com`. The tests:
- Process only recent emails (last 7-30 days)
- Clean up test data after each run
- Don't interfere with production data

## Understanding Test Output

### Successful Test
```
✅ Database has Gmail connection
   Found connection: rohanluthra13@gmail.com
   Status: active
   Created: 2024-01-15T10:30:00Z
```

### Failed Test
```
❌ Gmail API is accessible
   Error: Token refresh failed
```

### Summary
```
========================================
Test Summary:
========================================
Total: 30
Passed: 28 ✅
Failed: 2 ❌
========================================
```

## Troubleshooting Tests

### "No active Gmail connection found"
**Solution**: Connect Gmail through the UI first
```bash
docker-compose up
# Go to http://localhost:3000/dashboard
# Click "Connect Gmail"
```

### "Token refresh failed"
**Solution**: Reconnect Gmail (tokens may have expired)

### "Rate limit exceeded"
**Solution**: Wait a few minutes, Gmail API has quotas

### "Database connection failed"
**Solution**: Ensure PostgreSQL is running
```bash
docker-compose up db
```

### Tests hang or timeout
**Solution**: Check if services are running
```bash
docker-compose ps
```

## Writing New Tests

### Test Template
```typescript
import { setupTestContext, teardownTestContext, TestReporter } from './setup';

async function main() {
  console.log('🧪 Your Test Name');
  console.log('================\n');
  
  const reporter = new TestReporter();
  const context = await setupTestContext();
  
  try {
    await reporter.runTest('Test case name', async () => {
      // Your test logic
      if (somethingWrong) {
        throw new Error('What went wrong');
      }
      console.log('   Success message');
    });
    
  } finally {
    await teardownTestContext(context);
    reporter.printSummary();
  }
}

if (require.main === module) {
  main().catch(console.error);
}
```

### Best Practices
1. **Clean up after tests** - Use teardownTestContext
2. **Use real data carefully** - Don't delete production data
3. **Handle async properly** - Use await for all async operations
4. **Provide clear output** - Log what's being tested
5. **Test edge cases** - Empty results, errors, etc.

## CI/CD Integration

To run tests in CI:

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:17
        env:
          POSTGRES_PASSWORD: subscription_pass
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
    
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-node@v2
      - run: npm install
      - run: npm run db:migrate:run
      - run: npm run test:integration
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          GMAIL_CLIENT_ID: ${{ secrets.GMAIL_CLIENT_ID }}
          # ... other secrets
```

## Performance Benchmarks

Expected test durations:
- Gmail OAuth: ~2-3 seconds
- Sync Pipeline: ~10-15 seconds (depends on emails)
- Subscription CRUD: ~3-5 seconds
- **Total**: ~20-25 seconds

## Security Notes

- Tests use real API credentials - keep `.env.test` secure
- Don't commit test outputs that might contain sensitive data
- Clean up test data to avoid leaking information

## Quick Commands Reference

```bash
# Run all tests
npm run test:integration

# Run with verbose output
DEBUG=* npm run test:integration

# Run specific test
tsx src/test/integration/gmail-oauth.test.ts

# Check what will be tested (dry run)
tsx src/test/integration/setup.ts

# Clean test data manually
tsx -e "
  import { DatabaseService } from './src/lib/db/service';
  const db = new DatabaseService();
  await db.db.delete(db.subscriptions).where(db.eq(db.subscriptions.userId, '1'));
"
```