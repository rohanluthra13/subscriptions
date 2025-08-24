# Email MCP Integration Plan

## Goal
Enrich incomplete subscription data (from user braindumps) with structured data extracted from email notifications using LLM analysis via MCP tools.

## The Enrichment Flow
```
Incomplete Subscriptions → Email Analysis → Complete Subscriptions
     (braindump)           (LLM-driven)        (structured)
```

## User Experience
1. User does braindump of subscription info (scratchpad or chat)
2. LLM creates structured subscription records (incomplete)
3. LLM automatically enriches records using email analysis
4. User has complete subscription data (renewal dates, pricing changes, etc.)

## Technical Architecture

### Current State
- ✅ User braindump → structured subscriptions (via MCP tools)
- ✅ Gmail OAuth + email metadata ingestion pipeline 
- ✅ GUI trigger for email metadata fetch
- ✅ MCP tools: get_subscriptions, add_subscription, update_subscription
- ✅ MCP tool for triggering email fetch (trigger_email_fetch)
- ✅ MCP tool for email status (get_email_status)
- ✅ Background job system for long-running operations
- ✅ Domain extraction and clustering from email metadata

### Missing Components
- 🔴 Email content reading (bodies, not just metadata)
- 🔴 Email filtering logic (identify subscription-relevant emails)
- 🔴 Content analysis prompts for data extraction
- 🔴 Automatic subscription enrichment workflow

## Implementation Phases

### Phase 1: MCP Email Fetch Tool ✅ COMPLETED
**Goal**: LLM can trigger email refresh autonomously
- ✅ `trigger_email_fetch()` MCP tool implemented
- ✅ Calls existing Gmail metadata pipeline
- ✅ Returns job ID for background processing
- ✅ `get_email_status()` tool for checking connection/stats

### Phase 2: Email Content Reading (Core Capability) 🔴 CRITICAL BLOCKER
**Goal**: Access full email bodies for analysis
- Modify `process_batch_simple()` to use `format=full` instead of `format=metadata`
- Add `content` field to `processed_emails` table
- Parse email body from Gmail API response (handle text/html parts)
- Consider storage implications (bodies are ~10-100x larger than metadata)

**Implementation Notes**:
- Gmail OAuth scope already supports content reading (`gmail.readonly`)
- Infrastructure exists (batch processing, retry logic, background jobs)
- Main change needed: Line 450 in main.py, change API format parameter

### Phase 3: Smart Email Filtering (Efficiency) 
**Goal**: LLM identifies subscription-relevant emails before reading content
- Subject line analysis (keywords: "payment", "renewal", "receipt")
- Sender domain matching (match against subscription domains)
- Date relevance filtering (recent emails for active subscriptions)
- LLM-based relevance scoring

### Phase 4: Content Analysis Prompts (Intelligence)
**Goal**: Extract structured data from email content
- MCP prompts for specific extractions:
  - "Extract renewal date from this email"
  - "Find pricing changes in subscription emails" 
  - "Identify payment failure notifications"
- Update subscription records with extracted data

### Phase 5: Auto-Enrichment Workflow (Automation)
**Goal**: End-to-end automated subscription enrichment
- LLM triggers email fetch
- Filters relevant emails
- Reads content for high-relevance emails
- Extracts structured data
- Updates subscription records
- Reports findings to user

## Key Technical Decisions

### Email Volume Strategy
- **Approach**: Filter first, then read content (efficiency)
- **Rationale**: Avoid reading thousands of irrelevant emails

### Email-to-Subscription Matching
- **Primary**: Domain-based matching (processed_emails.sender_domain ↔ subscriptions.domains)
- **Fallback**: LLM-based fuzzy matching for edge cases

### Data Storage
- **Email content**: Add `content` field to `processed_emails` table
- **Extracted data**: Update existing `subscriptions` fields
- **Analysis metadata**: Track confidence scores, extraction timestamps

## Success Criteria
1. **Autonomy**: LLM can enrich subscriptions without user intervention
2. **Accuracy**: >90% correct extraction of renewal dates, pricing
3. **Efficiency**: Process only relevant emails (not all email history)
4. **Completeness**: Fill in missing data fields for existing subscriptions

## Current Status & Next Steps

### ✅ What's Working
- Complete MCP server with 5 tools (subscriptions CRUD + email operations)
- Gmail OAuth and metadata ingestion for 1 year of emails
- Background job system for long-running operations
- Web UI at localhost:8000 for manual control
- Domain extraction and clustering from email senders

### 🔴 Critical Blocker: Email Content Reading
**The single change needed**: Modify line 450 in `main.py`:
```python
# Current (metadata only):
url = f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}?format=metadata'

# Needed (full content):
url = f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}?format=full'
```

Then add content storage and parsing. This unblocks the entire enrichment pipeline.