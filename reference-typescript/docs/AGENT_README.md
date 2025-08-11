# Agent Development Guide

This guide is designed for AI coding agents working on this codebase. It provides clear, actionable instructions for common tasks.

## Project Overview

**Subscription Tracker** - A web app that connects to Gmail, detects subscription emails, and helps users manage their recurring payments.

### Tech Stack
- **Frontend**: Next.js 14 (App Router), React, TypeScript, Tailwind CSS
- **Backend**: Next.js API Routes, Node.js
- **Database**: PostgreSQL with Drizzle ORM
- **Services**: Gmail API, OpenAI API
- **Infrastructure**: Docker, Docker Compose

## Quick Start Commands

```bash
# Start development environment
docker-compose up

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop everything
docker-compose down

# Reset database
npm run db:reset

# Run migrations
npm run db:migrate:run
```

## Project Structure

```
/src
├── app/                 # Next.js app router pages
│   ├── api/            # API endpoints
│   └── dashboard/      # Dashboard UI pages
├── components/         # React components
│   ├── ui/            # Shadcn UI components
│   └── dashboard/     # Dashboard-specific components
├── lib/               # Shared utilities
│   ├── api/          # API utilities
│   └── db/           # Database layer
├── services/          # Business logic
│   ├── gmail/        # Gmail integration
│   ├── llm/          # AI/LLM integration
│   └── processing/   # Sync pipeline
└── test/             # Test files
```

## Common Tasks

### 1. Adding a New API Endpoint

Create file in `src/app/api/[path]/route.ts`:

```typescript
import { NextRequest } from 'next/server';
import { createApiHandler } from '@/lib/api/middleware';
import { successResponse } from '@/lib/api/utils/response';

export const GET = createApiHandler(async (request: NextRequest) => {
  // Your logic here
  return successResponse({ data: 'result' });
});
```

### 2. Database Operations

Always use DatabaseService:

```typescript
import { DatabaseService } from '@/lib/db/service';

const db = new DatabaseService();

// Get data
const subs = await db.getSubscriptions({ userId: '1' });

// Create data
const sub = await db.createSubscription({ ... });

// Update data
await db.updateSubscription(id, { ... });
```

### 3. Adding UI Components

Use existing UI components from `src/components/ui/`:

```typescript
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
```

### 4. Working with Gmail

```typescript
import { GmailService } from '@/services/gmail/gmail-service';

const gmail = new GmailService(accessToken, refreshToken);
const emails = await gmail.getMessageList({ maxResults: 100 });
```

### 5. Testing Changes

```bash
# Type checking (ALWAYS run before committing)
npm run type-check

# Linting (ALWAYS run before committing)
npm run lint

# Run integration tests
npm run test:integration

# Manual testing
# 1. Start the app
# 2. Go to http://localhost:3000
# 3. Follow docs/testing/MANUAL_CHECKLIST.md
```

## Environment Variables

Create `.env.local` file:

```env
# Database
DATABASE_URL=postgresql://subscription_user:subscription_pass@localhost:5432/subscription_tracker

# Gmail OAuth
GMAIL_CLIENT_ID=your_client_id
GMAIL_CLIENT_SECRET=your_client_secret
REDIRECT_URI=http://localhost:3000/api/auth/gmail/callback

# OpenAI
OPENAI_API_KEY=your_api_key

# Encryption
ENCRYPTION_KEY=your_32_char_encryption_key_here!!
```

## Database Schema

Key tables:
- `users` - Single user for MVP
- `connections` - Gmail OAuth connections
- `subscriptions` - Detected subscriptions
- `processed_emails` - Email processing log
- `sync_jobs` - Sync job tracking

## API Endpoints

### Core Endpoints
- `POST /api/connections/gmail` - Start OAuth flow
- `GET /api/connections/status` - Check connection
- `POST /api/sync/manual` - Trigger sync
- `GET /api/subscriptions` - List subscriptions
- `PUT /api/subscriptions/[id]` - Update subscription
- `DELETE /api/subscriptions/[id]` - Delete subscription
- `GET /api/export` - Export data

## State Management

Frontend uses React hooks for state:
- `useConnection()` - Gmail connection status
- `useSubscriptions()` - Subscription data
- `useSyncStatus()` - Sync progress

## Error Handling

Always use ApiError class:

```typescript
import { ApiError, ErrorCode } from '@/lib/api/types/errors';

throw new ApiError(
  ErrorCode.NOT_FOUND,
  'Subscription not found',
  404
);
```

## Git Workflow

```bash
# Create feature branch
git checkout -b feature/your-feature

# Make changes and test
npm run type-check
npm run lint

# Commit with conventional commits
git add .
git commit -m "feat: add new feature"

# Push and create PR
git push origin feature/your-feature
```

## Debugging Tips

1. **Check Docker logs**: `docker-compose logs -f app`
2. **Database issues**: `npm run db:studio` opens Drizzle Studio
3. **Gmail issues**: Check OAuth credentials and redirect URI
4. **LLM issues**: Verify OpenAI API key and check rate limits
5. **Frontend issues**: Check browser console and network tab

## Performance Considerations

1. **Gmail API**: Limited to 250 quota units per user per second
2. **OpenAI API**: Costs ~$0.003 per email processed
3. **Database**: Indexes on userId, emailId for performance
4. **Frontend**: Use pagination for large lists

## Security Notes

1. **Never commit secrets** - Use environment variables
2. **Tokens are encrypted** - Using AES-256-GCM
3. **API uses middleware** - For auth and validation
4. **Input validation** - Using Zod schemas

## Deployment

```bash
# Build for production
npm run build

# Start production server
npm start

# Or use Docker
docker-compose -f docker-compose.prod.yml up
```

## Common Issues & Solutions

### Gmail won't connect
- Check redirect URI matches exactly
- Ensure app is in test mode or published
- Verify OAuth credentials

### Sync fails
- Check Gmail API quotas
- Verify OpenAI API key
- Look for errors in sync_jobs table

### Database errors
- Run migrations: `npm run db:migrate:run`
- Check DATABASE_URL is correct
- Ensure PostgreSQL is running

## Getting Help

1. Check existing code for patterns
2. Look at test files for examples
3. Read the docs in `/docs` folder
4. Check `DESIGN.md` for architecture

## Important Files to Know

- `/docs/architecture/DESIGN.md` - System design
- `/docs/planning/detail_workplan.md` - Project plan
- `/docs/testing/MANUAL_CHECKLIST.md` - Testing guide
- `/.env.example` - Environment template
- `/docker-compose.yml` - Docker setup

## Final Checklist Before Committing

- [ ] Code passes `npm run type-check`
- [ ] Code passes `npm run lint`
- [ ] Tested the changes locally
- [ ] No console.log statements left
- [ ] No hardcoded values (use env vars)
- [ ] No commented-out code
- [ ] Followed existing patterns
- [ ] Updated relevant documentation

Remember: This is an MVP. Prefer simple, working solutions over complex ones.