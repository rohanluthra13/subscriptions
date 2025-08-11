# Architectural Decision Log

This document records significant architectural decisions made during the development of the Subscription Tracker. Each decision includes context, options considered, and rationale.

## Decision Template

```markdown
### [ADR-XXX] Decision Title
**Date**: YYYY-MM-DD  
**Status**: Proposed | Accepted | Deprecated | Superseded  
**Deciders**: [List of people involved]  

#### Context
What is the issue that we're seeing that is motivating this decision?

#### Decision
What is the change that we're proposing and/or doing?

#### Consequences
What becomes easier or more difficult to do because of this change?

#### Alternatives Considered
- Option A: Description (Pros/Cons)
- Option B: Description (Pros/Cons)
```

---

## Decisions

### [ADR-001] Email Storage Strategy
**Date**: 2025-08-03  
**Status**: Proposed  
**Deciders**: TBD  

#### Context
Need to decide whether to store full email content locally or fetch on-demand like Zero email does. This affects storage costs, processing speed, privacy implications, and offline capabilities.

#### Recommendation
**On-Demand Fetching (Zero's Approach)**

Store only subscription metadata, fetch email content on-demand when needed. This is optimal for a subscription tracker where users interact with extracted data, not emails.

#### Detailed Analysis

**Option 1: Store Full Emails Locally**
- **Pros:**
  - Fast reprocessing when LLM models improve
  - Offline analysis capabilities
  - No API rate limit concerns for re-analysis
  - Better for debugging and manual review
- **Cons:**
  - High storage costs (avg 10-50GB per user)
  - Privacy concerns (storing sensitive data)
  - GDPR compliance complexity
  - Backup/restore complexity
- **Cost Impact:** ~$0.50-2.50/user/month for storage

**Option 2: On-Demand Fetching (Zero's approach)**
- **Pros:**
  - Minimal storage footprint
  - Better privacy (no email content stored)
  - Simpler GDPR compliance
  - Lower infrastructure costs
- **Cons:**
  - Slower user experience
  - Gmail API rate limits (250 quota units/user/second)
  - Requires internet for any operation
  - Can't improve extraction retroactively
- **Cost Impact:** ~$0.05/user/month for storage

**Option 3: Hybrid - Metadata + Temporary Cache (Recommended)**
- **Pros:**
  - Balance of performance and storage
  - Can reprocess recent emails without API calls
  - Lower storage than full retention
  - Privacy-friendly with auto-deletion
- **Cons:**
  - More complex implementation
  - Need cache eviction logic
  - Still some storage costs
- **Cost Impact:** ~$0.10-0.30/user/month

#### Consequences
- Simpler architecture with no cache management needed
- Better privacy compliance (no email content stored)
- Lower storage and infrastructure costs
- Must handle Gmail API rate limits gracefully
- "View in Gmail" links instead of inline email display
- Can re-fetch emails if LLM improvements require reprocessing

---

### [ADR-002] Single-User MVP vs Multi-User Architecture
**Date**: 2025-08-03  
**Status**: Proposed  
**Deciders**: TBD  

#### Context
Zero email has complex multi-user auth with OAuth providers, sessions, and permissions. Need to decide if we should build multi-user support from the start or focus on single-user for MVP.

#### Recommendation
**Single-User Code with Multi-User Database Schema**

Build single-user functionality but design the database with user_id foreign keys from day one. This allows fastest MVP development while avoiding painful migrations later.

#### Detailed Analysis

**Option 1: Pure Single-User**
- **Pros:**
  - Fastest to market (saves ~1-2 weeks)
  - No auth complexity (simple password or token)
  - Easier local development and testing
  - Perfect for self-hosted deployments
- **Cons:**
  - Massive migration pain to add multi-user later
  - Database schema changes affect all data
  - Can't easily add team/family features
  - Limited commercialization options
- **Development Time:** 3-4 weeks for MVP

**Option 2: Full Multi-User from Start**
- **Pros:**
  - No future migrations needed
  - Can add team accounts, sharing features
  - Ready for SaaS model
  - Proper isolation and security from day one
- **Cons:**
  - Adds 1-2 weeks to MVP timeline
  - Complex auth (need NextAuth or similar)
  - Over-engineering for initial use case
  - More testing scenarios
- **Development Time:** 5-6 weeks for MVP

**Option 3: Single-User Code + Multi-User Schema (Recommended)**
- **Pros:**
  - Fast MVP development (4 weeks)
  - No database migrations later
  - Easy to add auth layer when needed
  - Can hardcode user_id = 1 initially
- **Cons:**
  - Slight overhead in queries (WHERE user_id = ?)
  - Need to remember to include user_id
  - Some "dead" code initially
- **Development Time:** 4 weeks for MVP

#### Implementation Strategy
```sql
-- Every table includes user_id from day one
CREATE TABLE subscriptions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL DEFAULT '1', -- Hardcoded initially
  vendor_name TEXT NOT NULL,
  -- ... other fields
);

-- But skip complex auth tables initially
-- No need for: sessions, oauth_accounts, etc.
```

#### Consequences
- All queries must include user_id filter
- Need data access layer to enforce user isolation
- Can deploy as single-user immediately
- Multi-user upgrade requires only auth layer, not data layer

---

### [ADR-003] Processing Architecture: Real-time vs Batch
**Date**: 2025-08-03  
**Status**: Accepted  
**Deciders**: Rohan  

#### Context
Zero uses Google Pub/Sub for real-time email notifications with Cloudflare Durable Objects for processing. We need to decide our approach for processing emails for subscription detection, balancing simplicity, cost, and user experience.

#### Decision
**24-Hour Batch Processing with Manual Refresh**

Use daily batch processing (24-hour intervals) for MVP with manual refresh capability. This optimizes for cost and simplicity while providing user control.

#### Detailed Analysis

**Option 1: Real-time Processing (Pub/Sub + Webhooks)**
- **Pros:**
  - Instant subscription detection
  - Better user experience
  - Scales naturally with usage
  - No wasted API calls checking empty inboxes
- **Cons:**
  - Complex webhook setup and verification
  - Need public HTTPS endpoint
  - Harder local development
  - Must handle out-of-order delivery
  - Requires queue infrastructure
- **Complexity:** High - adds 1-2 weeks to MVP
- **Infrastructure:** Requires public URL, SSL, queue system

**Option 2: 6-Hour Batch Processing**
- **Pros:**
  - Good balance of responsiveness and simplicity
  - Reasonable delay (max 6 hours)
  - Still cost-effective
- **Cons:**
  - 4x more API calls than daily
  - More frequent processing overhead
  - Still some delay vs real-time
- **Cost:** ~$0.20/month API calls, medium complexity

**Option 3: 24-Hour Batch Processing + Manual Refresh (Chosen)**
- **Pros:**
  - Lowest ongoing API/LLM costs (75% reduction vs 6-hour)
  - Simplest infrastructure (single daily cron)
  - User control via manual refresh
  - Immediate value on onboarding (full historical sync)
  - Perfect for MVP simplicity
- **Cons:**
  - Up to 24-hour delay for new subscriptions
  - Requires user action for immediate updates
  - Less "magical" feeling than frequent auto-sync
- **Cost:** ~$0.05/month API calls, lowest complexity

#### Implementation Strategy
```javascript
// Dual-mode processor for onboarding and ongoing sync
class SubscriptionProcessor {
  // Initial sync: Process all historical emails (last 6 months)
  async processHistoricalEmails(connection) {
    const emails = await gmailApi.getHistoricalEmails(connection, { months: 6 });
    return await this.processEmails(emails);
  }
  
  // Daily sync: Process only new emails since last sync
  async processIncrementalEmails(connection) {
    const lastSync = connection.last_sync_at;
    const emails = await gmailApi.getRecentEmails(connection, { since: lastSync });
    return await this.processEmails(emails);
  }
  
  // Manual refresh: Same as incremental, triggered by user
  async processManualRefresh(connection) {
    return await this.processIncrementalEmails(connection);
  }
}

// Daily cron job
cron.schedule('0 6 * * *', async () => {
  const connections = await getActiveConnections();
  for (const connection of connections) {
    await processor.processIncrementalEmails(connection);
  }
});
```

#### Sync Strategy
1. **Onboarding:** Full historical sync (6 months) - immediate processing and results
2. **Daily Sync:** Automated daily cron at 6 AM UTC - incremental only
3. **Manual Refresh:** User-triggered incremental sync - same logic as daily

#### Consequences
- Significant cost reduction (75% fewer API/LLM calls vs 6-hour sync)
- Simpler infrastructure (single daily cron job)
- Immediate value on onboarding with full historical processing
- Users get control via manual refresh button
- Up to 24-hour delay for automatic subscription detection
- Need clear UX messaging about sync frequency
- Database tracking of last_sync_at timestamps critical
- Gmail API rate limits less of a concern with daily processing

---

### [ADR-004] LLM Integration Approach
**Date**: 2025-08-03  
**Status**: Accepted  
**Deciders**: Rohan  

#### Context
Need to use LLM to identify subscriptions from email content and extract structured data (vendor, amount, frequency, dates). We need to decide on the integration approach for single-user MVP focused on speed and simplicity.

#### Decision
**Direct Real-time API Calls with OpenAI**

Use OpenAI's real-time API with direct calls for immediate results. Design abstraction to support multiple providers later, but start simple for MVP.

#### Detailed Analysis

**Option 1: Direct Real-time API Calls (Chosen)**
- **Pros:**
  - Immediate results - perfect for MVP UX
  - Simple implementation (1-2 days vs 3-4 for batch)
  - Always latest model capabilities
  - Easy debugging and development
  - No job queue complexity
  - Works great for single-user volumes
- **Cons:**
  - Higher per-email cost (~$0.003 vs $0.0015)
  - Rate limits (not a concern for single user)
  - Network latency (acceptable for MVP)
- **Cost:** ~$0.30/month for typical user (100 emails)
- **Implementation:** 1-2 days

**Option 2: Batch API Processing**
- **Pros:**
  - 50% cost reduction from OpenAI
  - Better rate limit handling
  - Natural fit with batch email processing
- **Cons:**
  - 24-hour turnaround time (poor UX)
  - More complex error handling
  - Need job queue infrastructure
  - Over-optimization for MVP scale
- **Cost:** ~$0.15/month per user
- **Implementation:** 3-4 days

**Option 3: Local LLM (Ollama/llama.cpp)**
- **Pros:**
  - Zero API costs
  - Complete privacy
  - No rate limits
- **Cons:**
  - Requires 8-16GB RAM
  - Slower processing (2-10x)
  - Lower accuracy (70-80% of GPT-4)
  - Complex setup for users
- **Suitable for:** Future self-hosted option

**Option 4: Hybrid Approach**
- **Pros:**
  - Flexibility and optimization
- **Cons:**
  - Over-engineering for MVP
  - Adds complexity without clear benefit
- **Decision:** Save for later phases

#### Implementation Strategy
```typescript
// Simple, direct approach for MVP
interface LLMProvider {
  detectSubscription(email: Email): Promise<SubscriptionData | null>;
}

class OpenAIProvider implements LLMProvider {
  async detectSubscription(email: Email): Promise<SubscriptionData | null> {
    // Direct API call - immediate results
    const response = await openai.chat.completions.create({
      model: process.env.OPENAI_MODEL, // Model TBD - configurable via env
      messages: [{ role: 'user', content: buildPrompt(email) }],
      response_format: { type: 'json_object' }
    });
    
    return parseSubscriptionData(response);
  }
}

// Simple service for MVP
class LLMService {
  private provider = new OpenAIProvider();
  
  async processEmail(email: Email): Promise<SubscriptionData | null> {
    return this.provider.detectSubscription(email);
  }
}

// Migration path: Easy to add batch processing later
// interface LLMProvider {
//   detectSubscription(email: Email): Promise<SubscriptionData | null>;
//   batchDetect?(emails: Email[]): Promise<SubscriptionData[]>; // Add later
// }
```

#### Prompt Engineering Strategy
- Use structured output (JSON mode)
- Few-shot examples in prompt
- Confidence scores for detection
- Separate prompts for detection vs extraction

#### Consequences
- Fastest path to working MVP (saves 2-3 days)
- No complex job queue infrastructure needed
- Immediate user feedback on subscription detection
- Easy to debug and develop
- Cost acceptable for single-user scale (~$0.30/month)
- Can easily migrate to batch API later without major refactoring
- Provider abstraction enables future local LLM support
- Perfect for self-hosted single-user deployments

---

### [ADR-005] Infrastructure and Deployment Strategy
**Date**: 2025-08-03  
**Status**: Proposed  
**Deciders**: TBD  

#### Context
Zero uses Docker Compose with PostgreSQL, Valkey (Redis fork), and Cloudflare Workers. Need to decide our infrastructure approach balancing simplicity with scalability.

#### Recommendation
**Docker Compose with PostgreSQL + Optional Redis**

Use Docker Compose for easy self-hosting, PostgreSQL as primary database, and Redis only when needed for job queues (not initially).

#### Detailed Analysis

**Option 1: Simple Node.js Deployment**
- **Pros:**
  - Easiest to develop and debug
  - No containerization overhead
  - Works with any hosting provider
  - Fast local development
- **Cons:**
  - Harder to ensure consistent environments
  - Manual dependency management
  - Not cloud-native
  - Difficult to scale
- **Suitable for:** Quick prototypes only

**Option 2: Full Kubernetes Setup**
- **Pros:**
  - Industry standard for scaling
  - Great for multi-tenant SaaS
  - Auto-scaling and self-healing
  - Professional deployment
- **Cons:**
  - Massive overkill for MVP
  - Complex local development
  - Expensive to run
  - Steep learning curve
- **Timeline Impact:** Adds 2+ weeks

**Option 3: Docker Compose (Recommended)**
- **Pros:**
  - Perfect for self-hosting
  - Easy local dev with prod parity
  - Single command deployment
  - Can transition to K8s later
- **Cons:**
  - Limited to single-host initially
  - Need Docker knowledge
  - Container overhead
- **Components:**
  ```yaml
  services:
    app:
      build: .
      environment:
        - DATABASE_URL=postgresql://...
    postgres:
      image: postgres:17-alpine
      volumes:
        - postgres_data:/var/lib/postgresql/data
    # Redis only when job queue needed
    # redis:
    #   image: redis:7-alpine
  ```

#### Database Decision: PostgreSQL
- **Why PostgreSQL:**
  - Excellent JSON support for email data
  - Proven scalability
  - Great full-text search
  - Strong ecosystem (Prisma, Drizzle)
- **Why not alternatives:**
  - MySQL: Weaker JSON support
  - MongoDB: Overkill for structured data
  - SQLite: Limits multi-user growth

#### Caching Strategy
- **Phase 1:** No Redis (use PostgreSQL)
- **Phase 2:** Add Redis for job queue only
- **Phase 3:** Redis for caching if needed

#### Consequences
- Need Docker in development
- Design for containerization from start
- Keep infrastructure simple initially
- Plan connection pooling for PostgreSQL

---

### [ADR-006] MVP Feature Scope
**Date**: 2025-08-03  
**Status**: Proposed  
**Deciders**: TBD  

#### Context
Need to define exact MVP scope to meet 3-5 week timeline while delivering core value.

#### Recommendation
**Gmail-only, Single Account, Daily Sync**

Focus on core subscription detection for one Gmail account with daily batch processing. Polish these features before expanding.

#### Core MVP Features (Week 1-3)
1. **Gmail Integration**
   - Single Gmail account OAuth
   - Fetch last 6 months of emails
   - Store email metadata + cache

2. **Subscription Detection**
   - LLM-based detection
   - Extract: vendor, amount, frequency, dates
   - Confidence scoring
   - Manual override capability

3. **Basic Dashboard**
   - List all subscriptions
   - Sort by cost/date
   - Search by vendor
   - Mark as active/cancelled

4. **Data Management**
   - Export to CSV
   - Edit subscription details
   - Delete subscriptions

#### Phase 2 Features (Week 4-5)
- Renewal reminders
- Spending analytics
- Better categorization
- Improved UI/UX

#### Explicitly Excluded from MVP
- Multiple email accounts
- Real-time processing
- Email sending/notifications
- Team/sharing features
- Mobile app
- Direct cancellation
- OAuth for other providers

#### Key Simplifications
1. **Single Gmail Account:** No account switching UI
2. **Daily Batch + Manual:** Cron job every 24 hours + manual refresh button
3. **No User Auth:** Single user, simple password
4. **Basic UI:** Function over form
5. **English Only:** No i18n initially

#### Success Criteria
- Detect 90%+ of actual subscriptions
- Process 1000 emails in < 5 minutes
- Dashboard loads in < 2 seconds
- Zero manual setup after OAuth

#### Consequences
- Very focused initial release
- Clear upgrade path
- Can ship in 3-4 weeks
- Need clear roadmap communication

---

## Index by Category

### Architecture
- ADR-001: Email Storage Strategy
- ADR-002: User Architecture
- ADR-005: Infrastructure and Deployment

### Processing
- ADR-003: Processing Architecture
- ADR-004: LLM Integration

### Product
- ADR-006: MVP Feature Scope

### [More categories to be added as decisions are made]