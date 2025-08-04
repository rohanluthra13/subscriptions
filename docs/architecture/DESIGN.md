# Subscription Tracker - Technical Design Document

## Problem Statement
<!-- Source: README.md, PRD.md -->
Consumers lose track of their subscriptions, leading to unwanted charges and wasted money. This tool automatically detects and tracks subscriptions by analyzing Gmail inbox content using LLM technology, providing a clear dashboard of all recurring expenses.

## Architecture Overview
<!-- Aligned with ADR-001, ADR-003: Batch processing + On-demand fetching -->
The system follows a simplified batch processing architecture designed for single-user MVP with future multi-user scalability:

### System Components
```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Gmail API  │────▶│  Batch Cron  │────▶│  PostgreSQL │
│   (OAuth)   │     │  Processor   │     │  Database   │
└─────────────┘     └──────────────┘     └─────────────┘
       │                    │                     │
       │                    ▼                     │
       │            ┌──────────────┐             │
       │            │     LLM      │◀────────────┘
       │            │  (OpenAI)    │
       │            └──────────────┘
       │                    │
       │                    ▼
       │            ┌──────────────┐
       └───────────▶│   Next.js    │
                    │  Dashboard   │
                    └──────────────┘
```

### Key Architectural Principles
1. **On-Demand Email Fetching**: No email content stored - fetch from Gmail API when needed
2. **Daily Batch Processing**: Scheduled processing every 24 hours via cron + manual refresh
3. **Single-User MVP**: Hardcoded user_id='1' with multi-user schema foundation
4. **Direct LLM Calls**: Real-time OpenAI API calls during processing
5. **Minimal Infrastructure**: Docker Compose with PostgreSQL only

### Data Flow
1. **Authentication**: User authorizes Gmail access via OAuth (one-time)
2. **Onboarding Sync**: Full historical processing (6 months) during initial setup
3. **Daily Sync**: Cron job runs every 24 hours processing new emails only
4. **Manual Refresh**: User-triggered incremental sync via dashboard button
5. **Processing**: For unprocessed emails, fetch content and call LLM immediately
6. **Storage**: Save extracted subscription data to PostgreSQL
7. **Dashboard**: Display subscriptions with manual refresh capability

### Technology Stack
<!-- Source: zero_analysis.md recommendations + README.md -->

#### Core Stack
- **Runtime**: Node.js 20+ with TypeScript
- **Framework**: Next.js 14 (App Router)
- **Database**: PostgreSQL 17 with Drizzle ORM
- **Styling**: Tailwind CSS
- **Deployment**: Docker Compose

#### External Services
- **Email**: Gmail API v1
- **LLM**: OpenAI API (model TBD)
- **Auth**: Google OAuth 2.0

#### Development Tools
- **Package Manager**: npm
- **Testing**: Jest + React Testing Library
- **Linting**: ESLint + Prettier
- **Type Checking**: TypeScript strict mode

## Database Schema
<!-- Aligned with ADR-002: Single-user code + multi-user schema -->

```sql
-- Users table (multi-user foundation, single-user implementation)
CREATE TABLE users (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Insert default user for MVP
INSERT INTO users (id, email, name) VALUES ('1', 'default@localhost', 'Default User');

-- Gmail connections (adapted from Zero)
CREATE TABLE connections (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL DEFAULT '1',
  email TEXT NOT NULL,
  access_token TEXT NOT NULL,
  refresh_token TEXT NOT NULL,
  token_expiry TIMESTAMP NOT NULL,
  history_id TEXT, -- Gmail history ID for incremental sync
  last_sync_at TIMESTAMP,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Detected subscriptions (core business data)
CREATE TABLE subscriptions (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL DEFAULT '1',
  connection_id TEXT NOT NULL,
  
  -- Core subscription data
  vendor_name TEXT NOT NULL,
  vendor_email TEXT,
  amount DECIMAL(10,2),
  currency TEXT DEFAULT 'USD',
  billing_cycle TEXT, -- 'monthly', 'yearly', 'weekly', 'one-time'
  
  -- Important dates
  next_billing_date DATE,
  last_billing_date DATE,
  detected_at TIMESTAMP DEFAULT NOW(),
  
  -- Status and confidence
  status TEXT DEFAULT 'active', -- 'active', 'cancelled', 'paused', 'unknown'
  confidence_score DECIMAL(3,2), -- 0.00 to 1.00
  
  -- User modifications
  user_verified BOOLEAN DEFAULT FALSE,
  user_notes TEXT,
  
  -- Metadata
  category TEXT, -- 'streaming', 'software', 'news', 'fitness', 'other'
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (connection_id) REFERENCES connections(id) ON DELETE CASCADE
);

-- Email processing log (prevent duplicate processing)
CREATE TABLE processed_emails (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid(),
  connection_id TEXT NOT NULL,
  gmail_message_id TEXT UNIQUE NOT NULL,
  gmail_thread_id TEXT,
  subject TEXT,
  sender TEXT,
  received_at TIMESTAMP,
  processed_at TIMESTAMP DEFAULT NOW(),
  subscription_found BOOLEAN DEFAULT FALSE,
  subscription_id TEXT,
  confidence_score DECIMAL(3,2),
  processing_error TEXT,
  
  FOREIGN KEY (connection_id) REFERENCES connections(id) ON DELETE CASCADE,
  FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE SET NULL
);

-- Batch processing jobs (track sync progress)
CREATE TABLE sync_jobs (
  id TEXT PRIMARY KEY DEFAULT gen_random_uuid(),
  connection_id TEXT NOT NULL,
  job_type TEXT NOT NULL, -- 'initial_sync', 'incremental_sync', 'manual_sync'
  status TEXT DEFAULT 'running', -- 'running', 'completed', 'failed', 'cancelled'
  
  -- Progress tracking
  total_emails INT DEFAULT 0,
  processed_emails INT DEFAULT 0,
  subscriptions_found INT DEFAULT 0,
  errors_count INT DEFAULT 0,
  
  -- Metadata
  started_at TIMESTAMP DEFAULT NOW(),
  completed_at TIMESTAMP,
  error_message TEXT,
  
  FOREIGN KEY (connection_id) REFERENCES connections(id) ON DELETE CASCADE
);

-- Performance indexes
CREATE INDEX idx_subscriptions_user_status ON subscriptions(user_id, status);
CREATE INDEX idx_subscriptions_next_billing ON subscriptions(next_billing_date) WHERE status = 'active';
CREATE INDEX idx_processed_emails_connection ON processed_emails(connection_id, processed_at);
CREATE INDEX idx_processed_emails_gmail_id ON processed_emails(gmail_message_id);
CREATE INDEX idx_sync_jobs_status ON sync_jobs(status, started_at);
CREATE INDEX idx_connections_user_active ON connections(user_id, is_active);
```

## Core Processing Architecture

### Processing Engine Overview
The system uses a **single core processing pipeline** triggered by three different sources:

```
┌─────────────────┐    ┌──────────────────────────────────┐    ┌─────────────────┐
│   Trigger       │───▶│     Core Processing Pipeline     │───▶│    Results      │
│   Sources       │    │                                  │    │                 │
├─────────────────┤    │ 1. Gmail API (fetch metadata)   │    ├─────────────────┤
│ 1. Onboarding   │    │ 2. Email Content (on-demand)    │    │ • Subscriptions │
│ 2. Daily Cron   │───▶│ 3. LLM Detection (OpenAI)       │───▶│ • Progress      │
│ 3. Manual Sync  │    │ 4. Deduplication Logic          │    │ • Job Status    │
└─────────────────┘    │ 5. Database Operations          │    │ • Error Logs    │
                       └──────────────────────────────────┘    └─────────────────┘
```

## Core Workflows

### 1. Trigger Sources

#### 1.1 Onboarding Trigger (Full Historical Sync)
<!-- Aligned with ADR-003: Full 6-month sync during onboarding -->

```mermaid
sequenceDiagram
    participant User
    participant Dashboard
    participant API
    participant Gmail
    participant LLM
    participant DB
    
    User->>Dashboard: Visit application
    Dashboard->>User: Show connect Gmail button
    User->>Dashboard: Click "Connect Gmail"
    Dashboard->>API: Initiate OAuth flow
    API->>Gmail: Request authorization
    Gmail-->>User: Show consent screen
    User->>Gmail: Grant permissions
    Gmail-->>API: Return auth code
    API->>Gmail: Exchange for tokens
    API->>DB: Store connection (user_id='1')
    
    Note over API,DB: Start Historical Sync (6 months)
    API->>DB: Create initial sync job
    API->>Gmail: Get message list (last 6 months)
    Gmail-->>API: Message IDs (could be 1000+ emails)
    
    loop Process email batches (50 at a time)
        API->>Gmail: Batch fetch email content
        Gmail-->>API: Email data
        
        loop For each email
            API->>LLM: Detect subscription
            LLM-->>API: Subscription data or null
            alt Subscription found
                API->>DB: Save subscription
            end
            API->>DB: Log processed email
        end
        
        API-->>Dashboard: Update progress (real-time)
        Dashboard-->>User: Show progress bar
    end
    
    API->>DB: Mark sync job complete
    Dashboard-->>User: Show found subscriptions
```

#### 1.2 Daily Cron Trigger (Incremental Sync)
<!-- Aligned with ADR-003: Daily batch processing (24 hours) -->

```mermaid
sequenceDiagram
    participant Cron
    participant Processor
    participant Gmail
    participant LLM
    participant DB
    
    Cron->>Processor: Trigger daily sync (6 AM UTC)
    Processor->>DB: Get active connections
    Processor->>DB: Create incremental sync job
    
    loop For each connection
        Note over Processor,Gmail: Only process emails since last sync
        Processor->>DB: Get last_sync_at timestamp
        Processor->>Gmail: Get messages since last sync
        Gmail-->>Processor: New message IDs only
        
        alt New messages found
            loop For unprocessed messages
                Processor->>Gmail: Fetch email content
                Gmail-->>Processor: Email body/subject
                Processor->>LLM: Detect subscription
                LLM-->>Processor: Subscription data or null
                alt Subscription found
                    Processor->>DB: Save subscription
                end
                Processor->>DB: Log processed email
            end
        else No new messages
            Note over Processor: Skip processing, update timestamp
        end
        
        Processor->>DB: Update connection.last_sync_at
    end
    
    Processor->>DB: Mark sync job complete
```

**Cron Configuration:**
```javascript
// cron/sync.js
const cron = require('node-cron');

// Run daily at 6 AM UTC
cron.schedule('0 6 * * *', async () => {
  console.log('Starting daily incremental sync...');
  await runIncrementalSync();
}, {
  timezone: 'UTC'
});
```

#### 1.3 Manual Refresh Trigger (User-Initiated Sync)
<!-- User-triggered incremental sync -->

```mermaid
sequenceDiagram
    participant User
    participant Dashboard
    participant API
    participant Gmail
    participant LLM
    participant DB
    
    User->>Dashboard: Click "Refresh Subscriptions" button
    Dashboard->>API: POST /api/sync/manual
    API->>DB: Check if sync already in progress
    
    alt Sync in progress
        API-->>Dashboard: Error "Sync already running"
        Dashboard-->>User: Show "Already syncing" message
    else No sync in progress
        API->>DB: Create manual sync job
        API->>DB: Get active connection
        API->>DB: Get last_sync_at timestamp
        
        API-->>Dashboard: Sync started
        Dashboard-->>User: Show progress indicator
        
        Note over API,Gmail: Same logic as daily sync
        API->>Gmail: Get messages since last sync
        Gmail-->>API: New message IDs
        
        loop For unprocessed messages
            API->>Gmail: Fetch email content
            Gmail-->>API: Email data
            API->>LLM: Detect subscription
            LLM-->>API: Subscription data or null
            alt Subscription found
                API->>DB: Save subscription
            end
            API->>DB: Log processed email
            
            API-->>Dashboard: Update progress
            Dashboard-->>User: Update progress bar
        end
        
        API->>DB: Update connection.last_sync_at
        API->>DB: Mark sync job complete
        API-->>Dashboard: Sync complete + results summary
        Dashboard-->>User: Show "Found X new subscriptions"
    end
```

### 2. Core Processing Pipeline Implementation

The processing pipeline consists of two main service classes that handle the core email → subscription logic:

#### 2.1 Subscription Detection Service
<!-- Aligned with ADR-004: Direct OpenAI API calls -->

```typescript
// services/subscription-detector.ts
interface EmailData {
  id: string;
  subject: string;
  sender: string;
  body: string;
  receivedAt: Date;
}

interface SubscriptionData {
  vendor_name: string;
  vendor_email: string;
  amount?: number;
  currency?: string;
  billing_cycle?: 'monthly' | 'yearly' | 'weekly' | 'one-time';
  next_billing_date?: Date;
  confidence_score: number;
  category?: string;
}

class SubscriptionDetector {
  private openai = new OpenAI({ 
    apiKey: process.env.OPENAI_API_KEY 
  });

  async detectSubscription(email: EmailData): Promise<SubscriptionData | null> {
    const prompt = this.buildPrompt(email);
    
    try {
      const response = await this.openai.chat.completions.create({
        model: process.env.OPENAI_MODEL, // Model TBD - must be set in env
        messages: [{ role: 'user', content: prompt }],
        response_format: { type: 'json_object' },
        temperature: 0.1,
        max_tokens: 500
      });
      
      const result = JSON.parse(response.choices[0].message.content);
      
      // Only return if confidence is high enough
      if (result.is_subscription && result.confidence_score >= 0.7) {
        return {
          vendor_name: result.vendor_name,
          vendor_email: result.vendor_email || email.sender,
          amount: result.amount || null,
          currency: result.currency || 'USD',
          billing_cycle: result.billing_cycle || null,
          next_billing_date: result.next_billing_date ? new Date(result.next_billing_date) : null,
          confidence_score: result.confidence_score,
          category: this.categorizeVendor(result.vendor_name)
        };
      }
      
      return null;
    } catch (error) {
      console.error('LLM detection failed:', error);
      throw new Error(`Subscription detection failed: ${error.message}`);
    }
  }

  private buildPrompt(email: EmailData): string {
    return `
Analyze this email and determine if it's related to a subscription service.
Extract subscription details if found.

Email Data:
From: ${email.sender}
Subject: ${email.subject}
Body: ${email.body.substring(0, 1500)}

Instructions:
- Look for recurring charges, subscriptions, memberships, renewals
- Ignore one-time purchases unless they mention recurring billing
- Ignore newsletters without payment information
- Extract exact amounts and dates when possible

Response format (JSON):
{
  "is_subscription": boolean,
  "confidence_score": 0.0-1.0,
  "vendor_name": "string",
  "vendor_email": "string",
  "amount": number or null,
  "currency": "USD/EUR/etc" or null,
  "billing_cycle": "monthly/yearly/weekly/one-time" or null,
  "next_billing_date": "YYYY-MM-DD" or null,
  "reasoning": "brief explanation"
}`;
  }

  private categorizeVendor(vendorName: string): string {
    const categories = {
      streaming: ['netflix', 'spotify', 'disney', 'hulu', 'amazon prime'],
      software: ['adobe', 'microsoft', 'google', 'dropbox', 'github'],
      news: ['times', 'post', 'journal', 'news', 'magazine'],
      fitness: ['gym', 'fitness', 'peloton', 'strava'],
      // Add more categories as needed
    };

    const vendor = vendorName.toLowerCase();
    for (const [category, keywords] of Object.entries(categories)) {
      if (keywords.some(keyword => vendor.includes(keyword))) {
        return category;
      }
    }
    return 'other';
  }
}
```

#### 2.2 Gmail Service (On-Demand Fetching)
<!-- Aligned with ADR-001: On-demand fetching, no email storage -->

```typescript
// services/gmail.ts
class GmailService {
  private gmail: gmail_v1.Gmail;

  constructor(connection: Connection) {
    const auth = new google.auth.OAuth2();
    auth.setCredentials({
      access_token: connection.access_token,
      refresh_token: connection.refresh_token,
    });
    
    this.gmail = google.gmail({ version: 'v1', auth });
  }

  // Get email metadata only (for batch processing)
  async getMessageList(options: {
    maxResults?: number;
    pageToken?: string;
    query?: string;
  } = {}): Promise<gmail_v1.Schema$Message[]> {
    const query = options.query || 'in:inbox -in:spam -in:trash';
    
    const response = await this.gmail.users.messages.list({
      userId: 'me',
      maxResults: options.maxResults || 100,
      pageToken: options.pageToken,
      q: query
    });

    return response.data.messages || [];
  }

  // Fetch full email content on-demand
  async getMessage(messageId: string): Promise<EmailData> {
    const response = await this.gmail.users.messages.get({
      userId: 'me',
      id: messageId,
      format: 'full'
    });

    const message = response.data;
    const headers = message.payload?.headers || [];
    
    return {
      id: messageId,
      subject: this.getHeader(headers, 'Subject') || '',
      sender: this.getHeader(headers, 'From') || '',
      body: this.extractBody(message.payload),
      receivedAt: new Date(parseInt(message.internalDate || '0'))
    };
  }

  // Incremental sync using history API
  async getHistoryList(startHistoryId: string): Promise<gmail_v1.Schema$History[]> {
    const response = await this.gmail.users.history.list({
      userId: 'me',
      startHistoryId,
      labelId: 'INBOX'
    });

    return response.data.history || [];
  }

  private getHeader(headers: gmail_v1.Schema$MessagePartHeader[], name: string): string | undefined {
    return headers.find(h => h.name?.toLowerCase() === name.toLowerCase())?.value;
  }

  private extractBody(payload?: gmail_v1.Schema$MessagePart): string {
    if (!payload) return '';

    // Handle multipart emails
    if (payload.parts) {
      for (const part of payload.parts) {
        if (part.mimeType === 'text/plain' || part.mimeType === 'text/html') {
          return this.decodeBody(part.body?.data || '');
        }
      }
    }

    // Handle single part emails
    if (payload.body?.data) {
      return this.decodeBody(payload.body.data);
    }

    return '';
  }

  private decodeBody(data: string): string {
    return Buffer.from(data, 'base64url').toString('utf8');
  }
}
```

#### 2.3 Processing Pipeline Orchestrator

```typescript
// services/sync-orchestrator.ts
class SyncOrchestrator {
  constructor(
    private gmailService: GmailService,
    private subscriptionDetector: SubscriptionDetector,
    private database: DatabaseService
  ) {}

  // Core processing pipeline - used by all trigger sources
  async processEmails(
    connection: Connection,
    emailIds: string[],
    syncJob: SyncJob
  ): Promise<ProcessingResult> {
    const results = {
      processed: 0,
      subscriptions_found: 0,
      errors: 0
    };

    for (const emailId of emailIds) {
      try {
        // Step 1: Check if already processed
        const alreadyProcessed = await this.database.isEmailProcessed(emailId);
        if (alreadyProcessed) continue;

        // Step 2: Fetch email content on-demand
        const email = await this.gmailService.getMessage(emailId);

        // Step 3: Smart filtering (cost optimization)
        if (!this.shouldProcessEmail(email)) {
          await this.database.logProcessedEmail(emailId, false);
          continue;
        }

        // Step 4: LLM detection
        const subscription = await this.subscriptionDetector.detectSubscription(email);

        // Step 5: Save results
        if (subscription) {
          // Check for duplicates
          const existing = await this.database.findDuplicateSubscription(subscription);
          if (!existing) {
            await this.database.saveSubscription(subscription, connection.id);
            results.subscriptions_found++;
          }
        }

        // Step 6: Log processing
        await this.database.logProcessedEmail(emailId, !!subscription, subscription?.id);
        results.processed++;

        // Step 7: Update progress
        await this.database.updateSyncJobProgress(syncJob.id, results);

      } catch (error) {
        results.errors++;
        await this.database.logProcessingError(emailId, error.message);
      }
    }

    return results;
  }

  // Different trigger entry points
  async processOnboarding(connection: Connection): Promise<SyncJob> {
    const syncJob = await this.database.createSyncJob(connection.id, 'initial_sync');
    const emailIds = await this.gmailService.getHistoricalEmails(6 * 30); // 6 months
    await this.processEmails(connection, emailIds, syncJob);
    return await this.database.completeSyncJob(syncJob.id);
  }

  async processDailySync(connection: Connection): Promise<SyncJob> {
    const syncJob = await this.database.createSyncJob(connection.id, 'incremental_sync');
    const emailIds = await this.gmailService.getEmailsSince(connection.last_sync_at);
    await this.processEmails(connection, emailIds, syncJob);
    await this.database.updateConnectionLastSync(connection.id);
    return await this.database.completeSyncJob(syncJob.id);
  }

  async processManualRefresh(connection: Connection): Promise<SyncJob> {
    const syncJob = await this.database.createSyncJob(connection.id, 'manual_sync');
    const emailIds = await this.gmailService.getEmailsSince(connection.last_sync_at);
    await this.processEmails(connection, emailIds, syncJob);
    await this.database.updateConnectionLastSync(connection.id);
    return await this.database.completeSyncJob(syncJob.id);
  }

  private shouldProcessEmail(email: EmailData): boolean {
    // Smart filtering logic (from LLM Cost Optimization section)
    const subject = email.subject.toLowerCase();
    const sender = email.sender.toLowerCase();
    
    const skipPatterns = ['newsletter', 'promotional', 'sale', 'deal', 'social media'];
    if (skipPatterns.some(pattern => subject.includes(pattern))) return false;
    
    const priorityPatterns = ['subscription', 'billing', 'invoice', 'receipt', 'payment', 'renewal'];
    return priorityPatterns.some(pattern => subject.includes(pattern) || sender.includes(pattern));
  }
}
```

## API Design
<!-- Simplified REST API for MVP -->

### Authentication
```typescript
// Simplified single-user auth for MVP
const API_KEY = process.env.API_KEY || 'dev-key-123';

function authenticateRequest(req: Request): boolean {
  const apiKey = req.headers['x-api-key'] || req.query.api_key;
  return apiKey === API_KEY;
}
```

### Core Endpoints

#### 1. Gmail Connection Management
```typescript
// POST /api/connections/gmail
// Initialize Gmail OAuth flow
interface ConnectGmailRequest {
  redirect_uri?: string;
}

interface ConnectGmailResponse {
  auth_url: string;
  state: string;
}

// GET /api/connections/gmail/callback?code=...&state=...
// Handle OAuth callback
interface CallbackResponse {
  success: boolean;
  connection_id: string;
  email: string;
}
```

#### 2. Sync Management
```typescript
// POST /api/sync/manual
// Trigger manual refresh (incremental sync)
interface ManualSyncRequest {
  connection_id?: string; // Optional - defaults to user's connection
}

interface ManualSyncResponse {
  job_id: string;
  status: 'started';
  message: 'Manual sync started - checking for new emails';
}

// GET /api/sync/jobs/:job_id
// Check sync progress (works for all sync types)
interface SyncJobStatus {
  id: string;
  job_type: 'initial_sync' | 'incremental_sync' | 'manual_sync';
  status: 'running' | 'completed' | 'failed';
  progress: {
    total_emails: number;
    processed_emails: number;
    subscriptions_found: number;
    errors_count: number;
  };
  started_at: string;
  completed_at?: string;
  error_message?: string;
}

// GET /api/sync/status
// Check if any sync is currently running
interface SyncStatusResponse {
  is_syncing: boolean;
  current_job?: {
    job_id: string;
    job_type: string;
    started_at: string;
  };
  last_sync_at?: string;
  next_scheduled_sync: string; // Daily at 6 AM UTC
}
```

#### 3. Subscription Management
```typescript
// GET /api/subscriptions
// List subscriptions with filtering
interface ListSubscriptionsQuery {
  status?: 'active' | 'cancelled' | 'paused';
  category?: string;
  sort?: 'amount' | 'date' | 'name';
  order?: 'asc' | 'desc';
  search?: string;
  limit?: number;
  offset?: number;
}

interface ListSubscriptionsResponse {
  subscriptions: Subscription[];
  total: number;
  summary: {
    total_monthly: number;
    total_yearly: number;
    active_count: number;
  };
}

// PUT /api/subscriptions/:id
// Update subscription
interface UpdateSubscriptionRequest {
  status?: 'active' | 'cancelled' | 'paused';
  amount?: number;
  billing_cycle?: string;
  next_billing_date?: string;
  user_notes?: string;
  user_verified?: boolean;
}

// DELETE /api/subscriptions/:id
// Remove subscription
```

#### 4. Data Export
```typescript
// GET /api/export
// Export subscriptions
interface ExportQuery {
  format: 'csv' | 'json';
  status?: string;
  date_range?: string;
}

// Returns file download
```

### Error Handling
```typescript
interface ErrorResponse {
  error: {
    code: string;
    message: string;
    details?: Record<string, any>;
  };
}

// Standard error codes:
// - UNAUTHORIZED
// - GMAIL_API_ERROR
// - SYNC_IN_PROGRESS
// - SUBSCRIPTION_NOT_FOUND
// - VALIDATION_ERROR
```

## Infrastructure & Deployment
<!-- Aligned with ADR-005: Docker Compose -->

### Docker Compose Configuration
```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
      - DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD}@db:5432/subscriptions
      - GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
      - GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - OPENAI_MODEL=${OPENAI_MODEL}
      - API_KEY=${API_KEY}
      - NEXTAUTH_URL=${NEXTAUTH_URL:-http://localhost:3000}
      - NEXTAUTH_SECRET=${NEXTAUTH_SECRET}
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs

  db:
    image: postgres:17-alpine
    environment:
      - POSTGRES_DB=subscriptions
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  # Cron service for daily batch processing
  cron:
    build: .
    command: npm run cron
    environment:
      - NODE_ENV=production
      - DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD}@db:5432/subscriptions
      - GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
      - GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - OPENAI_MODEL=${OPENAI_MODEL}
      - CRON_TIMEZONE=UTC
      - SYNC_SCHEDULE=0 6 * * * # Daily at 6 AM UTC
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs

volumes:
  postgres_data:
```

### Environment Variables
```bash
# .env.example

# Database
POSTGRES_PASSWORD=secure-password-123

# Google OAuth (get from Google Cloud Console)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret

# OpenAI
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_MODEL=your-chosen-model  # TBD - any OpenAI chat completion model

# Application
API_KEY=your-secure-api-key-123
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=your-nextauth-secret-key

# Optional
LOG_LEVEL=info
SYNC_INTERVAL_HOURS=6
```

### Development Scripts
```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "cron": "node dist/cron/scheduler.js",
    "db:generate": "drizzle-kit generate",
    "db:push": "drizzle-kit push",
    "db:migrate": "drizzle-kit migrate",
    "db:studio": "drizzle-kit studio",
    "lint": "next lint",
    "type-check": "tsc --noEmit"
  }
}
```

## Security & Privacy
<!-- Aligned with privacy-first approach -->

### OAuth Security
```typescript
// Minimal Gmail OAuth scopes
const GMAIL_SCOPES = [
  'https://www.googleapis.com/auth/gmail.readonly',
  'https://www.googleapis.com/auth/userinfo.email'
];

// Token encryption (at rest)
const crypto = require('crypto');

function encryptToken(token: string): string {
  const cipher = crypto.createCipher('aes-256-cbc', process.env.ENCRYPTION_KEY);
  let encrypted = cipher.update(token, 'utf8', 'hex');
  encrypted += cipher.final('hex');
  return encrypted;
}

function decryptToken(encryptedToken: string): string {
  const decipher = crypto.createDecipher('aes-256-cbc', process.env.ENCRYPTION_KEY);
  let decrypted = decipher.update(encryptedToken, 'hex', 'utf8');
  decrypted += decipher.final('utf8');
  return decrypted;
}
```

### Data Privacy Implementation
1. **No Email Storage**: Email content never persisted to database
2. **Minimal Metadata**: Only store message IDs and processing status
3. **Data Retention**: Automatically clean up processed_emails older than 90 days
4. **Export/Delete**: Full GDPR compliance endpoints

## Performance Considerations

### Database Optimization
```sql
-- Connection pooling configuration
-- Max 10 connections for single-user MVP
DATABASE_URL="postgresql://user:pass@localhost:5432/db?connection_limit=10"

-- Key indexes for performance
CREATE INDEX CONCURRENTLY idx_subscriptions_active_billing 
ON subscriptions(user_id, status, next_billing_date) 
WHERE status = 'active';

CREATE INDEX CONCURRENTLY idx_processed_emails_recent 
ON processed_emails(connection_id, processed_at DESC);

-- Cleanup old processed emails (90 days)
CREATE OR REPLACE FUNCTION cleanup_old_processed_emails() 
RETURNS void AS $$
BEGIN
  DELETE FROM processed_emails 
  WHERE processed_at < NOW() - INTERVAL '90 days';
END;
$$ LANGUAGE plpgsql;
```

### Gmail API Optimization
```typescript
// Batch email fetching
async function batchFetchEmails(messageIds: string[]): Promise<EmailData[]> {
  const batchSize = 50; // Gmail API batch limit
  const batches = [];
  
  for (let i = 0; i < messageIds.length; i += batchSize) {
    const batch = messageIds.slice(i, i + batchSize);
    batches.push(batch);
  }
  
  const results = await Promise.all(
    batches.map(batch => 
      Promise.all(batch.map(id => this.getMessage(id)))
    )
  );
  
  return results.flat();
}

// Rate limiting with exponential backoff
async function withRetry<T>(
  operation: () => Promise<T>, 
  maxRetries: number = 3
): Promise<T> {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await operation();
    } catch (error) {
      if (error.code === 429 && attempt < maxRetries) {
        const delay = Math.pow(2, attempt) * 1000; // Exponential backoff
        await new Promise(resolve => setTimeout(resolve, delay));
        continue;
      }
      throw error;
    }
  }
  throw new Error('Max retries exceeded');
}
```

### LLM Cost Optimization
```typescript
// Smart email filtering before LLM processing
function shouldProcessEmail(email: EmailData): boolean {
  const subject = email.subject.toLowerCase();
  const sender = email.sender.toLowerCase();
  
  // Skip obvious non-subscriptions
  const skipPatterns = [
    'unsubscribe successful',
    'newsletter',
    'promotional',
    'sale',
    'deal',
    'offer ends',
    'social media',
    'calendar',
    'meeting'
  ];
  
  if (skipPatterns.some(pattern => subject.includes(pattern))) {
    return false;
  }
  
  // Prioritize likely subscription emails
  const priorityPatterns = [
    'subscription',
    'billing',
    'invoice',
    'receipt',
    'payment',
    'renewal',
    'charged',
    'auto-pay'
  ];
  
  return priorityPatterns.some(pattern => 
    subject.includes(pattern) || sender.includes(pattern)
  );
}
```

## Development Milestones
<!-- Aligned with ADR-006: 3-5 week timeline -->

### Week 1: Foundation & Core Infrastructure
- [x] Project setup (Next.js, TypeScript, Tailwind, Drizzle)
- [x] Database schema implementation
- [x] Docker Compose configuration
- [x] Gmail OAuth integration
- [x] Basic API structure with authentication

### Week 2: Batch Processing & LLM Integration
- [x] Gmail service with on-demand fetching
- [x] Batch processing cron scheduler
- [x] OpenAI integration for subscription detection
- [x] Database services for subscriptions and processing logs
- [x] Deduplication logic

### Week 3: Dashboard & User Interface
- [x] Subscription list view with search/filter
- [x] Subscription edit and delete functionality
- [x] Sync status and progress tracking
- [x] CSV export functionality
- [x] Basic responsive design

### Week 4: Polish & Production Ready
- [x] Error handling and validation
- [x] Performance optimization
- [x] Security hardening
- [x] Documentation and deployment guides
- [x] Testing and bug fixes

## Future Enhancements

### Phase 2 (Month 2)
- Real-time webhook processing (upgrade from batch)
- Multiple Gmail accounts per user
- Enhanced categorization with custom rules
- Basic spending analytics dashboard

### Phase 3 (Month 3)
- Multi-user authentication with NextAuth.js
- Email notifications for renewals
- Browser extension for direct subscription detection
- Mobile-responsive PWA enhancements

### Phase 4 (Month 4+)
- Other email providers (Outlook, Yahoo)
- Direct cancellation integration
- Team/family account sharing
- Advanced analytics and insights

---

*Document Version: 2.0*  
*Last Updated: 2025-08-03*  
*Status: Aligned with ADR decisions*