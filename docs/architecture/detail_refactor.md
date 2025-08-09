# Implementation Plan: 6-Phase Email Processing Pipeline

## Overview

This document outlines how to build a complete 5-phase email processing pipeline for subscription detection from scratch. The existing codebase uses a different workflow that needs to be refactored to implement the new architecture described in `workflow.md`. For MVP, we're skipping the pre-filtering phase to simplify implementation.

**Current Implementation Status:**
- ✅ Phase 1: Email Metadata Ingestion (COMPLETE - API deployed, tested end-to-end)
- ❌ Phase 2: Classification & Grouping (not started)
- ❌ Phase 3: Group Processing/Review (not started)
- ❌ Phase 4: Story Building (not started)
- ❌ Phase 5: Final Storage (partially exists, needs refactoring)

## Why This Incremental Approach

**Context**: Single-user MVP, not yet released, can make breaking changes freely.

**Core Strategy**: Build one piece at a time, test with real data, then add the next piece.

1. **Start Small**: 30 emails → test → works? → scale to 100
2. **Test Early**: Use real Gmail data from day 1
3. **Fix as We Go**: No need to prevent all possible failures upfront
4. **Ship Fast**: Get working subscription detection in 1-2 weeks

## The 5-Phase Processing Pipeline (MVP)

### Why We Need Multiple Phases

Each phase serves a distinct purpose and can be built/tested independently:

**Phase 1**: Email Fetching - Get email metadata from Gmail
**Phase 2**: Classification & Grouping - LLM analyzes each email and groups by vendor
**Phase 3**: Group Processing - Review/approve groups (auto-approve for MVP)
**Phase 4**: Story Building - LLM analyzes grouped emails: "What's the subscription timeline?"
**Phase 5**: Storage - Save final subscription records

### Why Multiple LLM Calls Are Needed

**Phase 2 LLM**: Individual email analysis
- Input: Single email
- Question: "Is this subscription-related? What vendor?"
- Output: `{ isSubscription: boolean, vendor: "Netflix", type: "billing" }`

**Phase 4 LLM**: Grouped email analysis  
- Input: All Netflix emails together
- Question: "What's the complete subscription story?"
- Output: `{ amount: 15.99, cycle: "monthly", status: "active", timeline: [...] }`

These are fundamentally different tasks requiring different prompts and context.

## Implementation Strategy: Build One Phase at a Time

### Phase 1: Email Metadata Ingestion
**Goal**: Fetch and store email metadata from Gmail

```typescript
// New implementation needed:
POST /api/sync/phase1 { limit: 30 }
→ Fetch email list from Gmail API
→ Store metadata (ID, subject, sender, date)
→ Display in UI for verification
→ No LLM processing yet
```

**Implementation Tasks**:
- ✅ Database schema (using existing `processed_emails` table + added `fetched_at`)
- ✅ Build Gmail API integration for list() calls (OAuth + token encryption)
- ✅ Create API endpoint for Phase 1 testing (`POST /api/sync/phase1`)
- ✅ Create API endpoint for metadata retrieval (`GET /api/sync/phase1/emails`)
- ✅ Add configurable limits (tested with 5 emails, supports 30/100/500)
- ✅ Deploy in Docker with working database connections
- ❌ Build UI to display fetched metadata

**Manual Test Milestone**: 
- ✅ Fetch emails and store metadata (tested with 5 real emails from Gmail)
- ✅ Verify subjects, senders, dates are correct (real data validated)
- ✅ Check that Gmail API integration works (OAuth + token encryption fixed)
- ✅ API endpoints respond correctly with proper JSON schemas
- ❌ Display fetched metadata in UI (pending)

**Database Schema (Completed)**:
```sql
-- Using existing processed_emails table with added column:
ALTER TABLE processed_emails 
ADD COLUMN fetched_at TIMESTAMP DEFAULT NOW();

-- Table includes all needed fields:
-- gmail_message_id, gmail_thread_id, subject, sender, received_at, fetched_at
```

### Phase 2: Classification & Grouping
**Goal**: Classify individual emails and group by vendor

#### Phase 2a: Content Fetch
```typescript
POST /api/sync/phase2a { emailIds: string[] }
→ Fetch full email content from Gmail
→ Extract text body and headers
```

#### Phase 2b: LLM Classification
```typescript
POST /api/sync/phase2b { emails: EmailData[] }
→ Process each email through LLM
→ Classify: subscription/not subscription
→ Extract vendor name if subscription
→ Store classifications
```

#### Phase 2c: Simple Grouping
```typescript
POST /api/sync/phase2c
→ Group emails by extracted vendor name
→ Simple string matching (case-insensitive)
→ Display groups in UI
```

**Implementation Tasks**:
- ❌ Build Gmail get() integration for full content
- ❌ Create LLM classification prompt
- ❌ Implement vendor extraction logic
- ❌ Build simple grouping algorithm
- ❌ Create UI to show grouped emails

**Manual Test Milestone**:
- Classify 30 emails from Phase 1
- Verify 70%+ accuracy on obvious subscriptions
- Check vendor grouping (Netflix emails together)
- Display groups in UI for verification

### Phase 3: Group Processing
**Goal**: Process groups (auto-approve for MVP)
```typescript
POST /api/sync/phase3
→ Auto-approve all groups from Phase 2
→ No user review for MVP
→ Pass groups to Phase 5
```

**Implementation Tasks**:
- ❌ Simple pass-through logic for MVP
- ❌ Future: Add optional review UI

**Manual Test Milestone**:
- Verify all groups proceed to next phase
- No data loss between phases

### Phase 4: Story Building
**Goal**: Build subscription timelines from grouped emails

```typescript
POST /api/sync/phase4 { groups: VendorGroup[] }
→ Send each group to LLM for timeline analysis
→ Extract: signup date, billing pattern, status
→ Build comprehensive subscription story
→ Calculate confidence scores
```

**Implementation Tasks**:
- ❌ Design LLM prompt for group analysis
- ❌ Handle token limits (max 10 emails per group)
- ❌ Extract timeline events chronologically
- ❌ Merge conflicting information
- ❌ Calculate overall confidence

**Manual Test Milestone**:
- Process 2-3 subscription groups
- Verify timeline extraction (signup, billings)
- Check amount and cycle detection
- Validate confidence scoring

### Phase 5: Final Storage
**Goal**: Save subscription stories to database

```typescript
POST /api/sync/phase5 { stories: SubscriptionStory[] }
→ Save all subscription data
→ Mark emails as processed
→ Display results in dashboard
```

**Implementation Tasks**:
- ❌ Save subscription records
- ❌ Update processed_emails table
- ❌ Create dashboard view
- ❌ Add edit/delete functionality

**Manual Test Milestone**:
- Save 2-3 subscriptions from Phase 4
- View in dashboard UI
- Edit/delete subscriptions
- Verify no duplicates on re-run

### Complete Pipeline Integration
**Goal**: Connect all 5 phases into single workflow

```typescript
POST /api/sync { limit: 30 }
→ Run Phase 1-5 sequentially
→ Track progress through each phase
→ Display final results
```

**Integration Tasks**:
- ❌ Create orchestrator to run all phases
- ❌ Add progress tracking UI
- ❌ Handle phase failures gracefully
- ❌ Add retry logic for failed phases

**Manual Test Milestone**:
- Run complete pipeline with 30 emails
- Verify 2-3 subscriptions detected
- Check end-to-end flow works
- Measure total processing time (<5 minutes)

## Error Handling & Recovery

**Critical Error Scenarios to Handle**:
- **LLM Rate Limits**: 30 emails × 3 seconds = potential rate limit issues
- **Partial Failures**: Pipeline fails at Phase 4, no way to resume
- **Data Inconsistencies**: Individual classification disagrees with story
- **Token Limit Exceeded**: Large email groups exceed LLM context window

**Required Implementations**:
```typescript
// Add transaction boundaries
await database.transaction(async (tx) => {
  const story = await buildStory(vendorGroup);
  await tx.saveSubscription(story);
  await tx.markEmailsProcessed(vendorGroup.emails);
});

// Add resume capability
interface SyncJob {
  phase: 1 | 2 | 3 | 4 | 5 | 6;
  processedEmails: string[];
  pendingGroups: VendorGroup[];
}

// Add LLM fallback
if (llmCall.failed && retries > 3) {
  // Save partial data, flag for manual review
  await savePartialSubscription(emailData, { needsReview: true });
}
```

**Test**:
- Simulate LLM failures and verify recovery
- Test with 100+ emails to trigger rate limits
- Verify partial failure doesn't corrupt data

## Database Schema (Current State)

**Phase 1 Complete**: Using existing `processed_emails` table with one addition:

```sql
-- Phase 1: Added for metadata tracking
ALTER TABLE processed_emails 
ADD COLUMN fetched_at TIMESTAMP DEFAULT NOW();
-- ✅ COMPLETED
```

**Existing schema already includes**:
- ✅ `users` table (defaults to id='1' for MVP)
- ✅ `connections` table (Gmail OAuth + sync tracking)
- ✅ `processed_emails` table (email metadata + processing state)
- ✅ `subscriptions` table (final subscription records)
- ✅ `sync_jobs` table (pipeline progress tracking)

**Future Phases** (will add columns as needed):
```sql
-- Phase 2: Classification results (TBD)
-- Phase 4: Story building data (TBD) 
-- Phase 5: Final subscription enhancements (TBD)
```

**Architecture Decision**: 
- ✅ Keep existing auth flow unchanged
- ✅ Reuse existing tables where possible
- ✅ Add columns incrementally per phase
- ✅ No new tables needed for MVP

## API Design (Incremental)

### Current API: Basic Sync (Already Implemented)
```typescript
POST /api/sync/manual
Body: { } // Uses default limits from existing implementation
Returns: {
  success: boolean,
  jobId: string,
  subscriptionsFound: number
}

GET /api/sync/jobs/:jobId  // Already implemented
Returns: {
  status: 'running' | 'completed' | 'failed',
  progress: { processed: 30, total: 30 }
}
```

### New API: User Review Flow
```typescript
POST /api/sync { limit: 30 }
Returns: {
  jobId: string,
  detectedSubscriptions: [
    {
      vendor: "Netflix",
      amount: 15.99,
      confidence: 0.9,
      sourceEmails: 3,
      needsReview: true
    }
  ]
}

POST /api/sync/:jobId/confirm
Body: {
  approvedSubscriptions: string[], // IDs to save
  rejectedSubscriptions: string[], // IDs to discard
  editedSubscriptions: EditedSubscription[] // Modified data
}

GET /api/subscriptions/:id/timeline  // New: story view
Returns: {
  vendor: "Netflix",
  timeline: [
    { date: "2024-01-15", event: "signup", amount: 15.99 },
    { date: "2024-02-15", event: "billing", amount: 15.99 }
  ],
  confidence: 0.9
}
```

## Testing Strategy

### Incremental Testing
**Step 1**: Verify email fetching
- Fetch 30 emails successfully
- No crashes or API errors
- Correct duplicate prevention

**Step 2**: Verify classification  
- LLM identifies obvious subscriptions (Netflix, Spotify)
- LLM rejects obvious non-subscriptions (newsletters, promotions)
- Reasonable accuracy (70%+ for obvious cases)

**Step 3**: Verify storage
- Subscriptions saved with correct data
- No duplicates created
- Data makes sense (amounts, vendors, dates)

**Step 4**: Scale testing
- 100 emails: completes in <2 minutes
- 500 emails: completes in <10 minutes
- 30 days: handles real email volume

### Manual Validation
- Use your own Gmail account with known subscriptions
- Compare detected subscriptions to actual ones
- Manually check false positives/negatives
- No automated testing needed for MVP

## Error Handling (Start Simple)

### Step 1-2: Basic Error Handling
```typescript
try {
  const result = await syncEmails(limit);
  return result;
} catch (error) {
  console.error('Sync failed:', error);
  return { error: 'Sync failed, please try again' };
}
```

### Step 3+: Enhanced Error Handling
- LLM timeout: 30 seconds
- LLM retry: 3 attempts with backoff
- Gmail API retry: 3 attempts for rate limits
- Partial failure: Continue with next email

## Success Criteria by Phase

### Phase 1 Success: Metadata Ingestion
- [x] Fetch emails from Gmail API (tested with 5 real emails)
- [x] Store metadata in database (`processed_emails` table ready)
- [x] API endpoints working (`POST /api/sync/phase1`, `GET /api/sync/phase1/emails`)
- [x] OAuth flow working with token encryption/decryption
- [x] Docker deployment with working database connections
- [ ] Display in UI with subjects, senders, dates
- [ ] Pagination works for larger email sets

### Phase 2 Success: Classification & Grouping
- [ ] Fetch full email content successfully
- [ ] LLM classifies with 70%+ accuracy
- [ ] Extract vendor names correctly
- [ ] Group emails by vendor in UI

### Phase 3 Success: Group Processing
- [ ] All groups proceed to Phase 4
- [ ] Future: User can review/edit groups

### Phase 4 Success: Story Building
- [ ] Build accurate timelines from groups
- [ ] Extract amounts and billing cycles
- [ ] Handle price changes and cancellations
- [ ] Generate confidence scores

### Phase 5 Success: Final Storage
- [ ] Save subscriptions without duplicates
- [ ] Display in dashboard with all details
- [ ] Allow editing and deletion
- [ ] Mark emails as processed

### Integration Success: Complete Pipeline
- [ ] Process 30 emails in <5 minutes
- [ ] Detect 70%+ of actual subscriptions
- [ ] Handle failures gracefully
- [ ] Show progress through all phases

## Future Enhancements (Post-MVP)

**Immediate** (Month 2):
- Cron scheduling for daily auto-sync
- Email metadata caching for performance
- User review interfaces for corrections
- Handle 6 months of emails

**Medium Term** (Month 3):
- Learning from user corrections
- Better duplicate detection
- Export to CSV
- Subscription analytics

**Long Term** (Month 4+):
- Multi-user support
- Other email providers
- Mobile app
- Direct cancellation links

## Critical Insights from Technical Review

### **Reality Check: What We're Building**
1. **All 5 phases need implementation**: Starting from scratch with new architecture
2. **Existing code needs refactoring**: Current workflow doesn't match pipeline design
3. **User control is essential**: 70-80% accuracy requires user review/correction
4. **Incremental approach**: Build and test each phase before moving to next

### **Why This Approach Works**
1. **Clean Architecture**: Build it right from the start
2. **Incremental Testing**: Validate each phase with real data
3. **Learn Early**: Test accuracy before building complex features
4. **User-Centric**: Add review interfaces to handle imperfect classification

### **Key Success Factors**
- **Acknowledge complexity**: Story building (Phase 4) requires substantial development
- **Plan for imperfection**: Build user correction workflows from day 1
- **Fix technical debt**: Remove hardcoded user IDs before scaling
- **Performance first**: Parallel LLM processing is essential for user experience

The key insight is that **useful subscription detection with user control** is better than **perfect automated detection**. Build for 70% accuracy + easy corrections rather than 95% accuracy with no user input.

---

*Document Version: 4.0*  
*Updated: 2025-08-09*  
*Status: Phase 1 COMPLETE - API deployed and tested end-to-end*  
*Key Changes: Phase 1 fully implemented with working Gmail API integration, OAuth flow, and Docker deployment. Successfully tested with real email data. Ready for Phase 2 or UI development.*