# Zero Email Architecture Analysis for Subscription Tracking Tool

## Overview
Zero Email is a full-featured email client built with React Router, Drizzle ORM, and Cloudflare Workers. It provides a solid foundation for building a subscription tracking tool, though we'll need to simplify many aspects for our focused use case.

## 1. Database Schema Analysis

### Core Email Tables
The schema uses PostgreSQL with Drizzle ORM and follows these patterns:

**Key Tables:**
- `user` - Basic user authentication and profile
- `connection` - OAuth connections to email providers (Google/Microsoft)
- `account` - Auth provider accounts (separate from email connections)
- `summary` - AI-generated email summaries with tags and suggested replies
- `note` - User notes attached to email threads

**Notable Design Decisions:**
- Uses text-based IDs (likely UUIDs) for all primary keys
- Stores OAuth tokens directly in the `connection` table
- No dedicated tables for emails/threads - appears to fetch from provider APIs on-demand
- AI summaries stored separately with `messageId` as primary key
- Extensive use of indexes for performance

### What We Should Adopt:
1. **Connection Management Pattern**: Their `connection` table elegantly handles multiple email accounts per user
2. **OAuth Token Storage**: Direct token storage with expiration tracking
3. **Summary Table Design**: Good pattern for storing AI-processed metadata

### What We Should Simplify:
1. **Remove Complex Auth**: We don't need the full `account`/`session`/`verification` system
2. **Skip User Settings**: The `userSettings`, `userHotkeys`, `writingStyleMatrix` are unnecessary
3. **No Templates/Drafts**: Remove `emailTemplate` and draft-related functionality

## 2. Gmail Integration Analysis

### Authentication & API Setup
```typescript
// Uses Google OAuth2Client with refresh tokens
this.auth = new OAuth2Client(env.GOOGLE_CLIENT_ID, env.GOOGLE_CLIENT_SECRET);
this.auth.setCredentials({
  refresh_token: config.auth.refreshToken,
  scope: this.getScope(),
});
```

### Sync Strategy
- **On-Demand Fetching**: No background sync - emails fetched when requested
- **History API Usage**: Uses Gmail History API for incremental updates
- **Batch Operations**: Supports batch label modifications
- **Rate Limiting**: Has built-in rate limit handling (see `gmail-rate-limit.ts`)

### Key Methods:
1. `listHistory()` - Incremental sync using historyId
2. `getThread()` - Fetches full thread with messages
3. `rawListThreads()` - Lists threads with pagination
4. `modifyLabels()` - Batch label operations

### Error Handling Pattern:
```typescript
withErrorHandler<T>(operation: string, fn: () => Promise<T>, context?: any)
```
Comprehensive error handling with automatic token refresh and connection cleanup on fatal errors.

## 3. Email Processing Pipeline

### Architecture:
1. **Pub/Sub Integration**: Uses Google Cloud Pub/Sub for real-time notifications
2. **Durable Objects**: Cloudflare Durable Objects for workflow state management
3. **Effect.ts**: Functional programming approach for pipeline orchestration

### Workflow Types:
- `MainWorkflow` - Processes Pub/Sub notifications
- `ThreadWorkflow` - Processes individual email threads
- `ZeroWorkflow` - Handles AI processing and enrichment

### Processing Flow:
1. Pub/Sub notification → MainWorkflow
2. Extract connectionId from subscription name
3. Fetch history changes from Gmail
4. Process each thread through ThreadWorkflow
5. AI enrichment in ZeroWorkflow

## 4. Docker Architecture

### Services:
```yaml
- PostgreSQL 17 (main database)
- Valkey (Redis fork for caching)
- Upstash Proxy (serverless Redis HTTP interface)
```

### Notable Choices:
- Uses Valkey instead of Redis (open-source fork)
- Upstash proxy for serverless Redis access
- No background job processors - all async via Cloudflare Workers

## 5. Code Organization

### API Structure:
```
src/
├── trpc/           # tRPC API routes
│   └── routes/     # Organized by feature
├── lib/            
│   ├── driver/     # Email provider interfaces
│   └── factories/  # Subscription factories
├── db/             # Database schema and migrations
└── pipelines/      # Workflow processing
```

### Design Patterns:
1. **Driver Pattern**: Abstract interface for email providers
2. **Factory Pattern**: Creates provider-specific subscriptions
3. **Repository Pattern**: Not used - direct Drizzle queries
4. **Middleware**: Auth validation at tRPC procedure level

## Recommendations for Subscription Tracking Tool

### 1. Database Schema Simplification
```sql
-- Core tables we need:
- users (simplified)
- connections (adopt as-is)
- subscriptions (new - detected subscriptions)
- subscription_emails (new - emails from subscriptions)
- processing_queue (new - for batch processing)
```

### 2. Gmail Integration Approach
- **Keep**: OAuth flow, token management, error handling
- **Simplify**: Remove draft/compose functionality
- **Add**: Subscription detection logic in email processing

### 3. Processing Pipeline
- **Adopt**: Pub/Sub for real-time notifications
- **Simplify**: Single workflow for subscription detection
- **Add**: Batch processing for initial sync
- **Consider**: Simple job queue instead of Durable Objects

### 4. Architecture Decisions
1. **Start Simple**: Monolithic API with background jobs
2. **Database First**: Store emails locally for processing
3. **Incremental Sync**: Use Gmail History API from the start
4. **Queue Everything**: Process emails asynchronously

### 5. Features to Skip Initially
- Multi-provider support (focus on Gmail only)
- Real-time UI updates
- Email composition/sending
- Complex AI features (writing style, etc.)
- OAuth application support

### 6. Key Patterns to Adopt
1. **Connection Management**: Multi-account support from day one
2. **Error Handling**: Comprehensive error recovery
3. **Rate Limiting**: Built-in Gmail API rate limit handling
4. **Modular Drivers**: Even if we only support Gmail initially

## Technical Debt to Avoid
1. **No Direct API Calls**: Always fetch through abstracted methods
2. **Don't Store Full Emails**: Store only what's needed for subscription tracking
3. **Avoid Tight Coupling**: Keep subscription logic separate from email fetching
4. **Plan for Scale**: Use pagination and cursors from the start

## Next Steps
1. Create simplified database schema focused on subscription tracking
2. Extract and adapt Gmail OAuth flow
3. Build minimal email processing pipeline
4. Implement subscription detection algorithms
5. Create simple web UI for subscription management