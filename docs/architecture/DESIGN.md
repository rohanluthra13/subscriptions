# Subscription Tracker - Technical Design Document

## Problem Statement
<!-- Source: README.md, PRD.md -->
<!-- Brief description of the problem we're solving and why -->

## Architecture Overview
<!-- Source: zero_analysis.md -->
<!-- High-level system design, major components, data flow -->

### System Components
<!-- Diagram showing: Gmail API → Processing Pipeline → LLM → Database → Web UI -->

### Technology Stack
<!-- Source: zero_analysis.md recommendations -->
<!-- Languages, frameworks, databases, external services -->

## Database Schema
<!-- Source: zero_analysis.md + our subscription-specific needs -->
<!-- Tables, relationships, indexes -->

```sql
-- Core tables design here
```

## Workflows

### 1. Initial Sync Workflow
<!-- Source: Design based on Zero's patterns -->
<!-- Steps, error handling, rate limiting -->

### 2. Real-time Processing Workflow
<!-- Source: Zero's pipeline architecture adapted -->
<!-- Webhook → Process → Classify → Store -->

### 3. Subscription Detection Workflow
<!-- Source: New design based on requirements -->
<!-- LLM prompts, classification logic, confidence scoring -->

## API Design
<!-- Source: Zero's tRPC patterns simplified -->
<!-- Endpoints, authentication, request/response formats -->

### Core Endpoints
- `GET /api/subscriptions` - List all subscriptions
- `POST /api/sync` - Trigger email sync
- `PUT /api/subscription/:id` - Update subscription status

## Security Considerations
<!-- Source: Zero's OAuth implementation -->
<!-- OAuth token storage, API security, data privacy -->

## Deployment Architecture
<!-- Source: Zero's docker-compose files -->
<!-- Container setup, environment variables, volumes -->

## Performance Considerations
<!-- Source: Zero's patterns + our scale requirements -->
<!-- Caching strategy, pagination, rate limits -->

## Development Milestones
<!-- Source: PLAN.md phases -->
1. Foundation - Gmail auth, basic schema
2. Processing - Email ingestion, LLM integration
3. Interface - Dashboard, management UI
4. Polish - Performance, error handling

## Open Questions
<!-- Source: PLAN.md discovery questions -->
<!-- List unresolved design decisions -->

---

*Document Version: 1.0*  
*Last Updated: [Date]*  
*Status: Draft*