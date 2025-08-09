# Email Processing Workflow Design

## Overview

This document provides a complete end-to-end guide to all workflows in the subscription tracking system. The core processing pipeline consists of six phases that process emails incrementally, designed for a single-user application with local storage.

**MVP Context:**
- **Pre-Launch**: No existing users, fresh database, can make breaking changes
- **Single User**: Personal use app, not enterprise software
- **Manual Sync Only**: No cron jobs or background processing initially
- **Incremental Testing**: Start with 30 emails, gradually increase to test scalability
- **Iterative Enhancement**: Build MVP, then add robustness over time

**Key Principles:**
- **Start Small**: Begin with 30 emails, then 100, then 500, then 30 days worth
- **Manual Control**: All processing triggered by user action
- **Simple State**: Just track if sync is running or not
- **No Blocking Reviews**: Process everything, show results, let user edit after
- **MVP Simplicity**: Get happy path working, defer all complexity

## System Workflows

### 1. Authentication Workflow (Gmail OAuth)
**Status**: ✅ Implemented and working

1. User clicks "Connect Gmail" button
2. System redirects to Google OAuth consent screen
3. User grants permissions (read-only Gmail access)
4. Google redirects back with auth code
5. System exchanges code for access/refresh tokens
6. Tokens stored encrypted in `connections` table
7. **Triggers**: Initial historical processing (Phase 1 with 6 months of data)

### 2. Processing Pipeline Triggers

The 6-phase processing pipeline has one simple trigger for MVP:

#### Manual Sync Trigger
- **When**: User clicks "Sync Emails" button
- **Scope**: Configurable limit for testing:
  - **Phase 1 Testing**: Last 30 emails
  - **Phase 2 Testing**: Last 100 emails
  - **Phase 3 Testing**: Last 500 emails
  - **Phase 4 Testing**: Last 30 days of emails
  - **Future**: Last 6 months (after optimization)
- **Purpose**: On-demand processing with full user control

**Note**: Cron scheduling and automatic syncing will be added after core pipeline is proven to work reliably.

## Core Processing Pipeline

The pipeline consists of six sequential phases that process emails based on data state:

### Pipeline Architecture

```
External Trigger                     Processing Pipeline
┌──────────────┐                    ┌──────────────────┐
│              │                    │                  │
│ Manual Sync  │───────────────────▶│  Phase 1:        │
│   Button     │                    │  Metadata        │
│              │                    │  Ingestion       │
└──────────────┘                    └────────┬─────────┘
                                              │
                                              ▼
                                    ┌──────────────────┐
                                    │  Phase 2:        │
                                    │  Pre-Filtering   │
                                    └────────┬─────────┘
                                              │
                                              ▼
                                    ┌──────────────────┐
                                    │  Phase 3:        │
                                    │  Classification  │
                                    │  & Grouping      │
                                    └────────┬─────────┘
                                              │
                                              ▼
                                    ┌──────────────────┐
                                    │  Phase 4:        │
                                    │  Human Review    │
                                    └────────┬─────────┘
                                              │
                                              ▼
                                    ┌──────────────────┐
                                    │  Phase 5:        │
                                    │  Story Building  │
                                    └────────┬─────────┘
                                              │
                                              ▼
                                    ┌──────────────────┐
                                    │  Phase 6:        │
                                    │  Final Storage   │
                                    └──────────────────┘
```

### Simple State Management

For MVP, we track minimal state:

**Sync Status Only:**
```typescript
interface SyncStatus {
  isRunning: boolean;
  currentPhase: number; // 1-6
  emailsProcessed: number;
  subscriptionsFound: number;
  lastSyncDate?: Date;
}
```

**No Blocking States:**
- Pipeline runs straight through all 6 phases
- No pausing for user review
- Groups are auto-created, user can merge/edit after
- Stories are auto-generated, user can correct after

**Simple Flow:**
- User clicks sync → Pipeline runs → Results shown
- User reviews results → Edits/merges as needed → Done

## Detailed Phase Descriptions

### Phase 1: Metadata Ingestion

**Purpose**: Fetch limited email metadata for processing.

**Operations**:
- Fetch email metadata via Gmail API `list()` calls
- **Apply configured limit** (30, 100, 500, or 30 days)
- For MVP, skip storing metadata - just pass to Phase 2
- Future: Add `email_metadata` table for caching

**Output**: List of email IDs to process

### Phase 2: Pre-Filtering

**Purpose**: Quick keyword filtering to reduce LLM calls.

**Operations**:
- Simple keyword check in subject/sender:
  - Include if contains: `subscription`, `billing`, `invoice`, `receipt`, `payment`, `renewal`
  - Skip if contains: `newsletter`, `promotion`, `sale`, `deal`, `offer`
- For MVP: No learning lists yet
- Future: Build inclusion/exclusion lists from user feedback

**Output**: Filtered email list (typically reduces by 50-70%)

### Phase 3: Email Classification & Grouping

**Purpose**: Classify each email and intelligently group by subscription vendor.

#### Phase 3a: Content Fetch
- Fetch full email content for marked emails only
- Use Gmail API `get()` with message IDs
- Extract text body and relevant headers

#### Phase 3b: Classification (One-by-One LLM Processing)
- Process each email individually through LLM
- Classify into categories:
  - Not subscription-related
  - Subscription start/signup
  - Subscription billing/receipt
  - Subscription cancellation
  - Subscription promo/offer
  - Subscription change (upgrade/downgrade)
- Extract vendor name for subscription emails

#### Phase 3c: Basic Extraction
- For subscription-classified emails, extract:
  - Vendor name (normalized)
  - Email type (from classification)
  - Confidence score

#### Phase 3d: Simple Grouping
- For MVP: Group by vendor name extracted in Phase 3b
- Simple string matching (case-insensitive)
- No LLM grouping initially - just exact vendor matches
- Future: Add LLM-powered fuzzy grouping

**Example**:
- "Netflix" emails → Netflix group
- "Spotify" emails → Spotify group
- Different capitalizations are merged

**Output**: Emails grouped by subscription vendor with classifications

### Phase 4: Group Processing (No Review)

**Purpose**: Auto-process groups without blocking.

**Operations**:
- All groups automatically proceed to Phase 5
- No user review required
- Groups saved to database for later editing

**Future Enhancement**:
- Add optional review step
- Allow user to merge/split groups after processing
- Build learning system from corrections

**Output**: All groups proceed to story building

### Phase 5: Subscription Story Building

**Purpose**: Build complete subscription lifecycle from grouped emails.

#### Phase 5a: Timeline Construction
For each confirmed subscription group:
- LLM analyzes all related emails together
- Builds chronological story:
  - Signup date and initial terms
  - Billing history and changes
  - Current status (active/cancelled)
  - Price changes over time

#### Phase 5b: Detail Extraction
Extract comprehensive subscription details:
- Current amount and billing cycle
- Last billing date
- Next expected billing date
- Active/cancelled status
- Total spent (if calculable)
- Service tier/plan name

#### Phase 5c: Confidence Scoring
- Rate confidence in extracted details
- Flag ambiguous or conflicting information

**Output**: Complete subscription stories with confidence scores

### Phase 6: Final Storage (No Review)

**Purpose**: Save all detected subscriptions.

**Operations**:
- Save all subscription stories to database
- Mark emails as processed
- No blocking for review

**Post-Processing** (User can do anytime):
- View all detected subscriptions
- Edit/correct any details
- Delete false positives
- Merge duplicates

**Storage**:
- Save all subscriptions (even uncertain ones)
- Let user clean up after

## Implementation Considerations

### MVP Approach

**What We're Building First:**
1. **Happy Path**: Focus on successful email processing flow
2. **Basic Error Handling**: Simple retry logic for LLM failures
3. **Manual Testing**: Validate functionality by hand, not automated testing
4. **Core Features**: Classification, grouping, user review, storage

**What We're Deferring:**
1. **Performance Optimization**: Will optimize after core functionality works
2. **Complex Error Recovery**: Advanced failure scenarios handled later
3. **Automated Testing Infrastructure**: Manual validation sufficient for MVP
4. **Edge Case Handling**: Focus on common subscription patterns first
5. **Multi-User Features**: Single user only for now

### LLM Processing Strategy

1. **Accuracy over cost**: Using best available models for accuracy
2. **Single email classification**: Each email processed individually for precision
3. **Group analysis**: Second pass analyzes all emails together for context
4. **Human verification**: Critical checkpoints ensure accuracy
5. **Simple Error Handling**: Retry failed LLM calls, log errors for manual review

### LLM Prompt Strategy

The pipeline uses LLM at three key points:

1. **Email Classification (Phase 3)**: Determine if email is subscription-related
2. **Vendor Grouping (Phase 3d)**: Group emails by subscription vendor
3. **Story Building (Phase 5)**: Extract subscription lifecycle from email groups

**Prompt Approach**:
- Use structured prompts with clear classification options
- Request structured output (JSON format) for easier parsing
- Include confidence scores for human review decisions
- Start with basic prompts, refine based on actual results

**See `detail_refactor.md`** for detailed prompt templates and implementation notes.

### Data Management

1. **Metadata persistence**: All email metadata stored permanently
2. **Content handling**: Email content fetched on-demand, not stored
3. **Processing logs**: Track all classification decisions
4. **Learning system**: Build vendor lists from user feedback
5. **Clean Migration**: No existing data to preserve, can replace old schema

### Scalability (Deferred)

1. **Batch processing**: Handle thousands of emails efficiently (post-MVP)
2. **Incremental updates**: Only process new emails after initial sync
3. **Smart caching**: Remember vendor patterns for future processing (post-MVP)
4. **Progressive enhancement**: System improves with each use

## Example Flows

### Testing Flow Examples

#### Phase 1 Test (30 emails)
1. User clicks "Sync Emails (Test: 30)"
2. **Phase 1-2**: Fetch 30 emails, filter to ~10-15
3. **Phase 3**: Classify 10-15 emails → find 2-3 subscriptions
4. **Phase 4-5**: Auto-group and build stories
5. **Phase 6**: Save results
6. **Result**: User sees 2-3 subscriptions detected
7. **Time**: ~30 seconds total

#### Phase 2 Test (100 emails)
1. User clicks "Sync Emails (Test: 100)"
2. Process ~30-40 emails after filtering
3. Detect 5-8 subscriptions
4. **Time**: ~2 minutes

#### Phase 3 Test (500 emails)
1. User clicks "Sync Emails (Test: 500)"
2. Process ~150-200 emails after filtering  
3. Detect 15-25 subscriptions
4. **Time**: ~10 minutes
5. **Optimization Point**: Add batching if too slow

#### Production (30 days)
1. After optimization from testing phases
2. Process last 30 days of emails
3. Full subscription detection
4. **Future**: Expand to 6 months once proven

## Integration with Existing Architecture

This workflow integrates with the existing system design:

- Replaces the current `SyncOrchestrator` with multi-phase pipeline
- Extends `processed_emails` table to store classifications
- Adds new `email_metadata` table for Phase 1
- Adds new `subscription_groups` table for Phase 3d
- Enhances `subscriptions` table with lifecycle data from Phase 5

### Simple Processing Flow

```typescript
// MVP: Single API endpoint for manual sync
export async function POST /api/sync(request) {
  const { limit = 30 } = request.body; // Default to 30 emails
  
  // Check if already running
  if (global.syncInProgress) {
    return { error: "Sync already in progress" };
  }
  
  try {
    global.syncInProgress = true;
    
    // Run all 6 phases sequentially
    const emails = await phase1_fetchEmails(limit);
    const filtered = await phase2_filter(emails);
    const classified = await phase3_classify(filtered);
    const groups = await phase4_group(classified);
    const stories = await phase5_buildStories(groups);
    const subscriptions = await phase6_save(stories);
    
    return { 
      success: true,
      processed: emails.length,
      found: subscriptions.length 
    };
    
  } finally {
    global.syncInProgress = false;
  }
}
```

## Implementation Roadmap

### Week 1: Core Pipeline
- [ ] Create simple sync endpoint
- [ ] Implement Phase 1-3 (fetch, filter, classify)
- [ ] Test with 30 emails
- [ ] Basic error handling

### Week 2: Complete Pipeline
- [ ] Implement Phase 4-6 (group, stories, save)
- [ ] Test with 100 emails
- [ ] Add progress tracking
- [ ] Simple results display

### Week 3: Scale Testing
- [ ] Test with 500 emails
- [ ] Add batching if needed
- [ ] Optimize slow parts
- [ ] Add edit/delete UI for subscriptions

### Week 4: Polish
- [ ] Test with 30 days of emails
- [ ] Improve accuracy
- [ ] Better error messages
- [ ] Documentation

## MVP vs Future Enhancements

### MVP Scope (What We're Building First)
- **Core Pipeline**: All 6 phases working end-to-end
- **Manual Sync Only**: One button to process emails
- **No Review Blocking**: Process everything, edit after
- **Incremental Testing**: Start with 30 emails, scale up
- **Simple UI**: Just show results, allow editing

### Deferred to Later Iterations

#### Performance & Scalability
- Advanced LLM call optimization and batching
- Sophisticated caching strategies
- Performance benchmarking and optimization
- Memory usage optimization for large email volumes

#### Robustness & Monitoring  
- Comprehensive error recovery and retry strategies
- Automated health monitoring and alerting
- Data consistency validation and repair
- Advanced logging and debugging tools

#### User Experience Enhancements
- Bulk operations for group management
- Advanced filtering and search capabilities
- Subscription analytics and insights
- Keyboard shortcuts and power-user features

#### Testing & Quality Assurance
- Automated testing infrastructure
- Continuous integration and deployment
- Regression testing and quality metrics
- Performance and load testing

## Next Steps

1. Review and approve this workflow design
2. Create database migration for new tables
3. Begin Implementation Phase I (Foundation & Database)
4. Focus on getting happy path working first

---

*Document Version: 3.0*  
*Updated: 2025-08-08*  
*Status: MVP-Focused E2E Workflow Design*