# Migration Plan: Personal Data Platform Evolution

This document outlines the phased migration from the current subscription tracking app to a comprehensive personal data platform with spaces architecture, automation, and memory capabilities.

## Motivation: Why Build a Personal Memory System?

The goal is to move from a 'traditonal application software' style to a 'LLM-enabled memory system'. The core concept is based around 3 memory types: short-term, long-term, and 'always back-of-mind'. 
- **short term memory**: represented by context windows of LLMs; workflows to enable user to easily orchestrate their LLMs
- **long term memory**: underlying data sourced from different inputs (e.g. email, files, connected apps) and supported by a vector database with embeddings above to enable semantic search. 
- **spaces (always back-of-mind)**: there are some things that we like to track, to keep an eye on. if we can have those here, supported by inputs and accessible via LLM, we can both remove ancilliary services from our lives (unnecessary subscriptions etc.) and allow LLM-augmentation (e.g. find alternative services, offer investment advice etc.)

This migration is to take our 'bare bones' subscription tracker and lay the foundations for a memory system. The key principles are simplicity and efficiency.

## Vision: From Subscription Tracker to Personal Memory System

Transform the current single-purpose tool into a **personal data platform** that serves as an externalized memory system with:
- **Raw Data Layer**: All inputs (emails, documents, files) stored in native formats
- **Vector Embeddings**: Semantic search across all personal data
- **Spaces**: Organized, domain-specific views (subscriptions, portfolio, finances)
- **LLM Integration**: AI agents with access to complete personal context
- **MCP Interface**: Standardized tool access for external AI agents

## Architecture Evolution Path

### Current State
```
Gmail OAuth → processed_emails → subscriptions (manual analysis)
```

### Target State
```
Raw Data (SQLite + MongoDB) → Vector Embeddings → Spaces → Unified Memory → MCP Tools
```

## Phase-by-Phase Implementation

---

## Phase 1: Foundation Migration 🏗️

**Goal**: Refactor existing architecture to support spaces without breaking current functionality

### Database Changes
```sql
-- Add spaces architecture
CREATE TABLE spaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,  -- 'structured', 'document', 'connection', 'base'
    storage_type TEXT,   -- 'sqlite', 'mongodb', 'virtual'
    config TEXT,         -- JSON configuration
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Modify existing tables to reference spaces
ALTER TABLE subscriptions ADD COLUMN space_id TEXT DEFAULT 'subscriptions';
ALTER TABLE processed_emails ADD COLUMN processing_status TEXT DEFAULT 'pending';

-- Initialize default spaces
INSERT INTO spaces VALUES
('subscriptions', 'Subscriptions', 'structured', 'sqlite', '{"schema": "subscriptions"}', CURRENT_TIMESTAMP),
('email_input', 'Email Input', 'connection', 'sqlite', '{"type": "gmail"}', CURRENT_TIMESTAMP);
```

### Code Changes
- Refactor `SubscriptionManager` to `SpaceManager` with subscription space as first implementation
- Update `docs/schema.md` to reflect spaces architecture
- Maintain existing API endpoints for backward compatibility
- Add space configuration system in Python

### Validation Criteria
- ✅ All existing functionality works unchanged
- ✅ Database supports spaces architecture
- ✅ Foundation ready for Phase 2 automation

---

## Phase 2: Subscriptions Automation 🤖

**Goal**: Implement LLM-powered subscription management with email automation

### Phase 2A: Manual Setup & Validation

#### Email Processing Pipeline
```python
# Cron job: every 15 minutes
gmail_processor.fetch_new_emails()
→ raw_emails (SQLite)
→ subscription_analyzer.process_pending()
→ LLM analysis with context
→ suggested_subscriptions (for user review)
→ confirmed_subscriptions (user-approved)
```

#### LLM Integration
- **Context Window Management**: Provide LLM with existing subscriptions for better detection
- **Confidence Scoring**: Track LLM certainty for manual review priority
- **Learning Loop**: User corrections improve future suggestions

#### MongoDB Integration
```javascript
// Store email attachments and LLM artifacts
collections: {
  email_attachments: {
    _id, email_id, filename, content_type, data, extracted_text
  },
  llm_analysis: {
    _id, email_id, analysis_type, prompt, response, confidence, timestamp
  },
  subscription_evidence: {
    _id, subscription_id, email_ids, confidence_score, analysis_summary
  }
}
```

#### Manual Review Interface
- New view: `/?view=automation`
- LLM suggestions with confidence scores
- One-click approve/reject with learning feedback
- Manual subscription creation with LLM assistance

### Phase 2B: LLM Discovery (Optional)

#### Autonomous Subscription Detection
- **Pattern Recognition**: Analyze email history for subscription indicators
- **Domain Clustering**: Group emails by sender domain with spending patterns
- **Suggestion Engine**: Proactively suggest subscriptions user might have missed
- **Confidence Thresholds**: Auto-approve high-confidence detections

#### Features
- Background analysis of existing email archive
- "Subscription health check" - find inactive/forgotten subscriptions
- Cost optimization suggestions based on usage patterns
- Renewal date predictions from email patterns

### Validation Criteria
- ✅ Cron jobs successfully process emails
- ✅ LLM accurately detects subscriptions (>80% accuracy after training)
- ✅ MongoDB stores attachments and analysis artifacts
- ✅ Manual review workflow reduces user effort by 70%
- ✅ System learns from user corrections

---

## Phase 3: Second Space (Portfolio Tracking) 📈

**Goal**: Validate multi-space architecture with portfolio management

### Portfolio Space Implementation
```sql
-- Portfolio-specific tables
CREATE TABLE positions (
    id TEXT PRIMARY KEY,
    space_id TEXT DEFAULT 'portfolio',
    symbol TEXT NOT NULL,
    shares DECIMAL(10,4),
    avg_cost_basis DECIMAL(10,2),
    current_price DECIMAL(10,2),
    portfolio_id TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE trades (
    id TEXT PRIMARY KEY,
    space_id TEXT DEFAULT 'portfolio',
    gmail_message_id TEXT,  -- Link to email source
    symbol TEXT NOT NULL,
    trade_type TEXT,        -- buy/sell/dividend/split
    shares DECIMAL(10,4),
    price DECIMAL(10,2),
    total_amount DECIMAL(10,2),
    trade_date DATE,
    broker TEXT,
    source TEXT DEFAULT 'email',  -- email/manual/csv
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Reuse Automation Infrastructure
- Same email processing pipeline
- Portfolio-specific LLM analyzers
- Cross-space email classification (subscription vs portfolio)
- CSV import capabilities for historical data

### Cross-Space Features
- **Relationship Tracking**: Link Netflix subscription to NFLX stock position
- **Unified Search**: "Show me all Netflix-related expenses and investments"
- **Cross-Space Insights**: "Your streaming subscriptions cost more than your tech stock dividends"

### Validation Criteria
- ✅ Portfolio space operates independently of subscriptions
- ✅ Shared automation infrastructure works for both spaces
- ✅ Cross-space relationships and search function correctly
- ✅ Users successfully manage two different data domains

---

## Future Phases: Memory System Evolution

### Phase 4: Vector Embeddings & Semantic Search
- Integrate Chroma/Qdrant for semantic search
- All raw data converted to embeddings
- Cross-space semantic queries: "Find things related to entertainment spending"

### Phase 5: Unified Memory Interface
- Context window management for LLM agents
- Memory retrieval workflows
- Attention mechanisms for relevant data surfacing

### Phase 6: Agent Ecosystem
- Enhanced MCP server with memory access
- Autonomous agents with personal context
- Workflow orchestration across spaces

## Technical Architecture Principles

### Data Flow Philosophy
```
Raw Input → Processing Pipeline → Space Storage → Unified Query → Agent Access
```

### Storage Strategy
- **SQLite**: Structured data with known schemas (subscriptions, portfolio)
- **MongoDB**: Flexible documents (email attachments, LLM artifacts)
- **Vector DB**: Semantic search across all data types
- **Unified Index**: Cross-space search without schema constraints

### HTML-over-the-Wire Compatibility
- Each space maintains its own templates and controllers
- Shared UI components for common patterns
- Server-side rendering preserves simplicity
- JavaScript only for navigation and UX enhancement

## Success Metrics

### Phase 1 (Foundation)
- Zero regression in existing functionality
- Clean spaces architecture implementation
- Documentation reflects new structure

### Phase 2 (Automation)
- 80%+ accuracy in subscription detection
- 70% reduction in manual subscription management effort
- Successful MongoDB integration for documents

### Phase 3 (Multi-Space)
- Portfolio tracking fully functional
- Cross-space features demonstrate architecture value
- User actively manages two different data domains

### Overall Success
- System becomes user's primary personal data interface
- AI agents have comprehensive personal context
- Memory system enables insights not possible before

## Risk Mitigation

### Complexity Management
- Incremental migration preserves working system at each phase
- Manual approval loops prevent automation errors
- Rollback plans for each phase

### Data Safety
- Complete backup before each phase
- Gradual migration of existing data
- Validation scripts to ensure data integrity

### User Adoption
- Existing workflows remain unchanged during migration
- New features are additive, not disruptive
- Clear value demonstration at each phase

---

This migration plan provides a structured path from the current subscription tracker to a comprehensive personal memory system, with clear validation criteria and risk mitigation at each phase.
