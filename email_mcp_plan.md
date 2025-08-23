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

### Missing Components
- 🔴 Email content reading (bodies, not just metadata)
- 🔴 MCP tool for triggering email fetch
- 🔴 Email filtering logic (identify subscription-relevant emails)
- 🔴 Content analysis prompts for data extraction

## Implementation Phases

### Phase 1: MCP Email Fetch Tool (Quick Win)
**Goal**: LLM can trigger email refresh autonomously
- Add `trigger_email_fetch()` MCP tool
- Calls existing Gmail metadata pipeline
- Returns status/count of new emails processed

### Phase 2: Email Content Reading (Core Capability)
**Goal**: Access full email bodies for analysis
- Extend Gmail API calls to fetch email content
- Store email bodies in `processed_emails` table
- Handle HTML/text content appropriately

**Key Questions**:
- Can current Gmail API setup read full email bodies?
- Storage implications for email content
- Privacy/security considerations

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

## Current Blocker
**Email Content Reading** - Need to extend Gmail API integration to fetch email bodies, not just metadata. This is the critical path for all subsequent phases.