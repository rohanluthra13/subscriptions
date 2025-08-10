# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Subscription Manager - An automated subscription tracking tool that processes Gmail inbox daily, identifies subscription-related emails using LLM processing, and extracts key subscription data. This is a single-user MVP with multi-user database schema foundation.

## Development Commands

### Essential Commands
```bash
# Development
npm run dev                 # Start Next.js development server
npm run build              # Build for production
npm run start              # Start production server

# Database Operations  
npm run db:generate        # Generate Drizzle migrations
npm run db:push           # Push schema changes to database
npm run db:migrate        # Run migrations
npm run db:studio         # Open Drizzle Studio
npm run db:seed           # Seed database with sample data
npm run db:reset          # Reset database completely

# Background Processing (Currently Disabled)
# npm run cron:start        # Placeholder - disabled during Phase 1
# npm run cron:dev          # Placeholder - disabled during Phase 1

# Code Quality
npm run lint              # ESLint check
npm run type-check        # TypeScript type checking

# Testing & Integration
npm run test:integration  # Run integration tests
```

### Single Test Execution
```bash
# Run specific integration test
tsx src/test/integration/gmail-oauth.test.ts
tsx src/test/integration/sync-pipeline.test.ts
```

## Architecture

### Core Components
- **Next.js 14 App Router** - Frontend framework
- **PostgreSQL + Drizzle ORM** - Database layer with type-safe queries
- **Gmail API** - Email access via OAuth 2.0  
- **OpenAI API** - LLM-powered subscription detection
- **node-cron** - Daily batch processing scheduler (disabled in Phase 1)

### Processing Pipeline
1. **Gmail OAuth** - One-time user authorization
2. **Email Fetching** - On-demand content retrieval (no storage)
3. **LLM Processing** - OpenAI API calls for subscription detection
4. **Data Storage** - Only subscription metadata stored (privacy-focused)
5. **Dashboard** - Web interface for subscription management

### Database Schema (Drizzle ORM)
Key tables in `src/lib/db/schema.ts`:
- `users` - Multi-user foundation (hardcoded user_id='1' for MVP)
- `connections` - Gmail OAuth tokens and sync state
- `subscriptions` - Detected subscription data
- `processedEmails` - Email processing log (prevents duplicates)
- `syncJobs` - Batch processing job tracking

### Project Structure
```
src/
├── app/                    # Next.js App Router pages
│   ├── api/               # API routes
│   └── dashboard/         # Dashboard pages
├── components/            # React components
│   ├── dashboard/         # Dashboard-specific components
│   ├── layout/           # Layout components
│   └── ui/               # Reusable UI components
├── hooks/                # Custom React hooks
├── lib/                  # Core libraries
│   ├── api/              # API utilities and middleware
│   ├── auth/             # Google OAuth implementation
│   ├── db/               # Database schema and services
│   ├── gmail/            # Gmail API client and utilities
│   └── llm/              # LLM classification logic
├── services-backup/      # Legacy service architecture (ignore)
└── test/                 # Integration tests
```

## Key Implementation Details

### Single-User MVP Pattern
- All user operations default to `user_id='1'`
- Database schema supports multi-user for future expansion
- No authentication middleware in MVP (simple API key)

### Email Processing Strategy
- **On-demand fetching** - No email content stored for privacy
- **Smart filtering** - Pre-LLM filtering to reduce API costs
- **Batch processing** - Daily cron job + manual refresh capability
- **Deduplication** - Prevents duplicate subscription detection

### LLM Integration
- OpenAI API for subscription detection in `src/lib/llm/classification.ts`
- Structured JSON responses with confidence scoring
- Cost optimization through email pre-filtering

### Error Handling
- Comprehensive error boundaries in API routes
- Gmail API rate limiting with exponential backoff
- Processing error logging in database

## Environment Setup

Required environment variables:
```bash
# Database
POSTGRES_PASSWORD=your-db-password

# Google OAuth (Google Cloud Console)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret

# OpenAI
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_MODEL=gpt-5-nano  # or preferred model

# Application
API_KEY=your-secure-api-key
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=your-nextauth-secret
```

## Development Workflow

### Database Changes
1. Modify schema in `src/lib/db/schema.ts`
2. Run `npm run db:generate` to create migration
3. Run `npm run db:push` to apply changes
4. Update service files in `src/lib/db/service.ts`

### API Development
- Routes in `src/app/api/` follow Next.js 14 App Router conventions
- Use middleware in `src/lib/api/middleware/` for common functionality
- Type definitions in `src/lib/api/types/`

### Component Development
- Use existing UI components from `src/components/ui/`
- Follow Tailwind CSS patterns from existing components
- Dashboard components in `src/components/dashboard/`

## Testing

### Integration Tests
- Located in `src/test/integration/`
- Test Gmail OAuth flow and sync pipeline
- Use `npm run test:integration` to run all tests

### Manual Testing Checklist
- Gmail connection and OAuth flow
- Email processing and subscription detection
- Dashboard CRUD operations
- CSV export functionality

## Docker Deployment

### Development
```bash
docker-compose -f docker-compose.dev.yml up
```

### Production
```bash
docker-compose up -d
```

Services:
- `app` - Next.js application
- `db` - PostgreSQL database
- `cron` - Background job scheduler (placeholder - disabled in Phase 1)

## Common Patterns

### Database Queries
```typescript
// Use service layer for database operations
import { db } from '@/lib/db';
import { subscriptions } from '@/lib/db/schema';

// Always use Drizzle's type-safe queries
const userSubscriptions = await db.query.subscriptions.findMany({
  where: eq(subscriptions.userId, '1'),
  with: { connection: true }
});
```

### Gmail API Calls
```typescript
// Use the service layer in src/lib/gmail/service.ts
import { GmailService } from '@/lib/gmail/service';

const gmail = new GmailService(connection);
const messages = await gmail.getMessageList({ maxResults: 50 });
```

### LLM Processing
```typescript
// Use classification service in src/lib/llm/classification.ts
import { classifyEmail } from '@/lib/llm/classification';

const result = await classifyEmail(emailContent);
if (result.isSubscription && result.confidence > 0.7) {
  // Process subscription
}
```

## Privacy & Security Notes

- **No email content storage** - All email data fetched on-demand
- **Minimal metadata** - Only store message IDs and processing status
- **OAuth tokens encrypted** - Store access/refresh tokens securely
- **GDPR compliance** - Support for data export and deletion
- **Rate limiting** - Protect against API abuse

## Known Issues & Limitations

- Single user implementation (user_id='1' hardcoded)
- Gmail API rate limits may affect large initial syncs
- OpenAI API costs scale with email volume
- No automated batch processing yet (cron disabled in Phase 1)
- Manual sync only via dashboard button