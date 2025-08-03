# Subscription Manager - Development Plan

## Overview
Build a lightweight subscription tracking tool that monitors Gmail, uses LLM to identify subscriptions, and provides insights through a dashboard.

## Development Approach
Start by deeply understanding Zero's email architecture, then adapt and simplify it for subscription tracking needs.

## Discovery Phase

### 1. **Analyze Zero's Architecture**
Key areas to investigate:
- How do they structure email data? (`src/db/schema.ts`)
- What's their Gmail sync strategy? (`src/lib/driver/google.ts`)
- How do they process emails? (background jobs, queues)
- What patterns do they use for error handling?
- How is their Docker setup structured?

### 2. **Extract Core Patterns**
From Zero's approach, identify:
- Minimal tables needed for email ingestion
- Authentication flow for Gmail
- Processing pipeline architecture
- Deployment configuration

### 3. **Design Subscription-Specific Architecture**
Based on Zero's patterns, determine:
- What to keep (email storage, sync logic)
- What to modify (processing pipeline for LLM)
- What to add (subscription-specific tables)
- What to remove (email UI, sending capabilities)

### Discovery Phase Outputs
1. **`zero_analysis.md`** - Analysis of Zero email architecture with recommendations
2. **`DESIGN.md`** - Technical design document for subscription tracker
3. **`DECISIONS.md`** - Log of architectural decisions and trade-offs

## Implementation Phases

### Foundation (Based on Discovery)
- Set up project structure informed by Zero's architecture
- Implement Gmail integration adapted from Zero's approach
- Create database schema combining Zero's email tables + subscription needs

### Core Processing
- Build email processing pipeline (simplified from Zero)
- Add LLM classification layer
- Create subscription data extraction

### Interface
- Dashboard for subscription insights
- Management capabilities

### Deployment
- Docker setup inspired by Zero's configuration
- Self-hosting focus

## Key Questions to Answer During Discovery

1. **Email Storage**: How much email data do we need to store? Just metadata or full content?
2. **Processing**: Real-time or batch? How does Zero handle this?
3. **Schema Design**: What's the minimal set of tables needed?
4. **Authentication**: Can we simplify Zero's auth for single-user MVP?
5. **Performance**: What are Zero's strategies for handling large email volumes?

## Resources
- Zero email codebase: `reference/zero-email/`
- Focus areas:
  - `src/db/schema.ts` - Database design
  - `src/lib/driver/google.ts` - Gmail integration
  - `docker-compose.*.yaml` - Deployment setup
  - `src/routes/` - API structure