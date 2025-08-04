# Subscription Tracker - Detailed Work Plan

## Overview
This plan breaks down the implementation into independent projects that can be worked on by single agents. Each project has clear deliverables, dependencies, and can be developed in isolation before integration.

## Project Structure

### P1: Core Infrastructure Setup
**Owner**: Infrastructure Agent  
**Duration**: 2-3 days  
**Dependencies**: None  
**Status**: ✅ **COMPLETED**

#### Deliverables:
1. **Next.js 14 Project Scaffold** ✅ **COMPLETED**
   - ✅ Initialize Next.js 14 with App Router
   - ✅ Configure TypeScript with strict mode
   - ✅ Set up Tailwind CSS
   - ✅ Configure ESLint and Prettier
   - ✅ Create project structure (src/, app/, components/, services/, lib/)

2. **Environment Configuration** ✅ **COMPLETED**
   - ✅ Create `.env.example` with all required variables
   - ✅ Set up environment validation
   - ✅ Configure Next.js for environment variables

3. **Docker Setup** ✅ **COMPLETED**
   - ✅ Create Dockerfile for Next.js app
   - ✅ Create docker-compose.yml with services:
     - `app`: Next.js application
     - `db`: PostgreSQL 17
     - `cron`: Batch processor service
   - ✅ Configure health checks and volumes
   - ✅ Create development docker-compose override

4. **Base Configuration Files** ✅ **COMPLETED**
   - ✅ `tsconfig.json` with proper paths
   - ✅ `package.json` with all scripts
   - ✅ `.gitignore` for Node.js/Next.js
   - ✅ Basic README with setup instructions

**Success Criteria**: ✅ **ALL MET**
- ✅ `docker-compose up` starts all services
- ✅ Next.js app runs on http://localhost:3000
- ✅ TypeScript compilation passes

---

### P2: Database Layer
**Owner**: Database Agent  
**Duration**: 2 days  
**Dependencies**: P1 (can start schema design in parallel)  
**Status**: ✅ **COMPLETED**

#### Deliverables:
1. **Drizzle Setup** ✅ **COMPLETED**
   - ✅ Install and configure Drizzle ORM
   - ✅ Create database connection configuration
   - ✅ Set up Drizzle schema and client generation

2. **Database Schema Implementation** ✅ **COMPLETED**
   - ✅ Implement full schema from DESIGN.md:
     - `users` table (single user MVP)
     - `connections` table (Gmail OAuth)
     - `subscriptions` table (core business data with 2-field status model)
     - `processed_emails` table (processing log)
     - `sync_jobs` table (batch tracking)
   - ✅ Create all indexes for performance
   - ✅ Add database migrations

3. **Database Service Layer** ✅ **COMPLETED**
   - ✅ Create `DatabaseService` class with methods:
     - Connection management (CRUD)
     - Subscription operations (create, update, find duplicates, batch operations)
     - Email processing logs
     - Sync job tracking
   - ✅ Implement connection pooling
   - ✅ Add transaction support

4. **Seed Data & Scripts** ✅ **COMPLETED**
   - ✅ Create seed script for development
   - ✅ Database reset script (`npm run db:reset`)
   - ✅ Migration scripts (`npm run db:migrate:run`)

**Success Criteria**: ✅ **ALL MET**
- ✅ All tables created with proper relationships
- ✅ Drizzle schema generates without errors
- ✅ Basic CRUD operations work
- ✅ Enhanced with 2-field subscription status model for real-world complexity

---

### P3: Gmail Integration Service
**Owner**: Gmail Agent  
**Duration**: 3 days  
**Dependencies**: P1, P2 (for storing connections)  
**Status**: ✅ **READY TO START** (dependencies complete)

#### Deliverables:
1. **OAuth 2.0 Implementation**
   - Set up Google OAuth client
   - Create OAuth flow endpoints:
     - `/api/auth/gmail/connect`
     - `/api/auth/gmail/callback`
   - Handle token refresh logic
   - Store encrypted tokens in database

2. **Gmail Service Class**
   - Implement `GmailService` with methods:
     - `getMessageList()` - fetch email metadata
     - `getMessage()` - fetch full email content
     - `getHistoricalEmails()` - for onboarding
     - `getEmailsSince()` - for incremental sync
   - Add proper error handling for API limits
   - Implement exponential backoff

3. **Email Data Models**
   - Create TypeScript interfaces for email data
   - Add email parsing utilities
   - Handle multipart emails

4. **Testing Utilities**
   - Mock Gmail API responses
   - Create test email datasets
   - Rate limit testing

**Success Criteria**:
- OAuth flow completes successfully
- Can fetch and parse emails from Gmail
- Handles API errors gracefully

---

### P4: LLM Integration Service
**Owner**: AI Agent  
**Duration**: 2 days  
**Dependencies**: P1  
**Status**: ✅ **READY TO START** (dependencies complete)

#### Deliverables:
1. **OpenAI Service Setup**
   - Configure OpenAI client
   - Create abstraction layer for future providers
   - Handle API key management

2. **Subscription Detection Service**
   - Implement `SubscriptionDetector` class:
     - `detectSubscription()` method
     - Structured prompt engineering
     - JSON response parsing
     - Confidence scoring logic
   - Category classification system
   - Smart email filtering (pre-LLM)

3. **Prompt Templates**
   - Create optimized prompts for:
     - Subscription detection
     - Data extraction
     - Confidence scoring
   - Include few-shot examples
   - Test with various email formats

4. **Cost Optimization**
   - Email pre-filtering logic
   - Token usage tracking
   - Batch processing preparation (future)

**Success Criteria**:
- Accurately detects subscriptions from test emails
- Extracts all required fields
- Maintains <$0.003 per email cost

---

### P5: Processing Pipeline
**Owner**: Backend Agent  
**Duration**: 3 days  
**Dependencies**: P2, P3, P4  
**Status**: Waiting for P3, P4 (P2 complete)

#### Deliverables:
1. **Sync Orchestrator Service**
   - Implement `SyncOrchestrator` class:
     - `processEmails()` - core pipeline
     - `processOnboarding()` - 6-month historical
     - `processDailySync()` - incremental
     - `processManualRefresh()` - user-triggered
   - Deduplication logic
   - Progress tracking

2. **Batch Processing System**
   - Create cron job scheduler
   - Implement job queue (using database)
   - Add job status tracking
   - Handle concurrent job prevention

3. **Processing Pipeline Steps**
   - Email fetching coordination
   - LLM processing pipeline
   - Database save operations
   - Error handling and logging

4. **Background Worker**
   - Separate Node.js process for cron
   - Daily sync scheduling (6 AM UTC)
   - Job monitoring and alerts

**Success Criteria**:
- Can process 1000 emails in <5 minutes
- Handles errors without data loss
- Tracks progress accurately

---

### P6: API Layer
**Owner**: API Agent  
**Duration**: 2 days  
**Dependencies**: P2, P5  
**Status**: Blocked by dependencies

#### Deliverables:
1. **Core API Endpoints**
   - Gmail connection endpoints
   - Sync management endpoints:
     - `POST /api/sync/manual`
     - `GET /api/sync/status`
     - `GET /api/sync/jobs/:id`
   - Subscription CRUD endpoints:
     - `GET /api/subscriptions`
     - `PUT /api/subscriptions/:id`
     - `DELETE /api/subscriptions/:id`
   - Export endpoint: `GET /api/export`

2. **API Middleware**
   - Simple authentication (API key for MVP)
   - Request validation
   - Error handling middleware
   - Rate limiting

3. **Response Formats**
   - Standardized JSON responses
   - Error response format
   - Pagination support
   - Progress streaming for long operations

4. **API Documentation**
   - OpenAPI/Swagger spec
   - Request/response examples
   - Error code documentation

**Success Criteria**:
- All endpoints return correct data
- Proper error handling
- API documentation complete

---

### P7: Frontend Dashboard
**Owner**: Frontend Agent  
**Duration**: 4 days  
**Dependencies**: P1, P6  
**Status**: Blocked by dependencies

#### Deliverables:
1. **Layout & Navigation**
   - App shell with header/sidebar
   - Responsive layout (desktop/tablet)
   - Loading states
   - Error boundaries

2. **Gmail Connection Flow**
   - Connect Gmail button
   - OAuth redirect handling
   - Connection status display
   - Onboarding progress UI

3. **Subscription List View**
   - Table/card view toggle
   - Sorting (by amount, date, name)
   - Search functionality
   - Filter by status/category
   - Pagination or virtualization

4. **Subscription Management**
   - Edit subscription modal
   - Delete confirmation
   - Bulk actions
   - Manual refresh button with progress

5. **Data Export**
   - Export button
   - Format selection (CSV/JSON)
   - Download handling

6. **Dashboard Components**
   - Summary statistics
   - Upcoming renewals
   - Monthly cost breakdown
   - Sync status indicator

**Success Criteria**:
- All user stories from PRD implemented
- Responsive on desktop/tablet
- <2 second load time

---

### P8: Integration & Testing
**Owner**: QA Agent  
**Duration**: 3 days  
**Dependencies**: All projects (P1-P7)  
**Status**: Blocked by all

#### Deliverables:
1. **Integration Testing**
   - End-to-end flow testing
   - Gmail OAuth flow verification
   - Processing pipeline validation
   - API endpoint testing

2. **Performance Testing**
   - Load testing with 1000+ emails
   - Database query optimization
   - Frontend performance audit
   - Memory leak detection

3. **Security Hardening**
   - Token encryption verification
   - API authentication testing
   - OWASP security checklist
   - Environment variable validation

4. **Documentation**
   - Deployment guide
   - Environment setup guide
   - Troubleshooting guide
   - API usage examples

**Success Criteria**:
- All integration tests pass
- Performance meets requirements
- Security audit passed

---

### P9: Production Deployment
**Owner**: DevOps Agent  
**Duration**: 2 days  
**Dependencies**: P8  
**Status**: Final phase

#### Deliverables:
1. **Production Configuration**
   - Production docker-compose
   - Environment variable setup
   - SSL/TLS configuration
   - Backup scripts

2. **Monitoring Setup**
   - Application logs
   - Error tracking (Sentry)
   - Basic metrics
   - Health check endpoints

3. **Deployment Scripts**
   - Build and deploy scripts
   - Database migration runner
   - Rollback procedures
   - Zero-downtime deployment

4. **Operations Documentation**
   - Runbook for common issues
   - Monitoring dashboard
   - Backup/restore procedures
   - Scaling guidelines

**Success Criteria**:
- Application deployed and accessible
- Monitoring active
- Backup verified

---

## Dependency Graph

```
P1 (Infrastructure)
├── P2 (Database)
│   ├── P5 (Processing Pipeline)
│   │   └── P6 (API Layer)
│   │       └── P7 (Frontend)
│   └── P6 (API Layer)
├── P3 (Gmail)
│   └── P5 (Processing Pipeline)
├── P4 (LLM)
│   └── P5 (Processing Pipeline)
└── P7 (Frontend)

P8 (Integration) depends on all
P9 (Deployment) depends on P8
```

## Parallel Development Opportunities

### Phase 1 (Can start immediately):
- P1: Infrastructure Setup
- P2: Database Layer (schema design only)
- P4: LLM Integration (prompt engineering)

### Phase 2 (After P1):
- P2: Database Layer (full implementation)
- P3: Gmail Integration
- P4: LLM Integration (full implementation)
- P7: Frontend (UI components only)

### Phase 3 (After P2, P3, P4):
- P5: Processing Pipeline
- P7: Frontend (API integration)

### Phase 4 (After P5):
- P6: API Layer
- P7: Frontend (complete)

### Phase 5 (After all):
- P8: Integration & Testing
- P9: Production Deployment

## Resource Allocation

### Recommended Team Structure:
1. **Backend Developer**: P2, P3, P5, P6
2. **Frontend Developer**: P1, P7
3. **Full-stack Developer**: P4, P8, P9

### Single Developer Approach:
Follow the dependency order, focusing on one project at a time. Estimated total time: 20-25 days.

## Success Metrics

Each project should meet its success criteria before moving to dependent projects. Key overall metrics:

1. **Functionality**: All features from PRD implemented
2. **Performance**: Process 1000 emails in <5 minutes
3. **Reliability**: 99%+ success rate for email processing
4. **User Experience**: Dashboard loads in <2 seconds
5. **Cost**: <$0.50/month per user for all services

## Risk Mitigation

### Technical Risks:
1. **Gmail API Limits**: Implement proper rate limiting and backoff
2. **LLM Accuracy**: Extensive prompt testing with real emails
3. **Performance**: Database indexing and query optimization
4. **Security**: Token encryption and secure storage

### Project Risks:
1. **Dependency Delays**: Start parallel work where possible
2. **Integration Issues**: Continuous integration testing
3. **Scope Creep**: Stick to MVP features only
4. **Testing Time**: Allocate sufficient time for P8

## Next Steps

1. Review and approve this plan
2. Set up project tracking (Linear, Jira, etc.)
3. Assign agents/developers to projects
4. Create detailed tickets for each deliverable
5. Begin with P1, P2 (schema), and P4 (prompts) in parallel