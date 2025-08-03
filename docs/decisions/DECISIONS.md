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

### [ADR-001] Use Gmail API Direct Fetch Instead of Email Storage
**Date**: 2025-08-03  
**Status**: Proposed  
**Deciders**: TBD  

#### Context
Need to decide whether to store full email content locally or fetch on-demand like Zero email does.

#### Decision
[To be filled after team discussion]

#### Consequences
[To be analyzed]

#### Alternatives Considered
- Store full emails: Better for offline analysis, higher storage costs
- Store only metadata: Lower storage, requires internet for re-analysis
- Hybrid approach: Store temporarily for processing, then delete

---

### [ADR-002] Single-User MVP vs Multi-User Architecture
**Date**: 2025-08-03  
**Status**: Proposed  
**Deciders**: TBD  

#### Context
Zero email has complex multi-user auth. Need to decide complexity level for MVP.

#### Decision
[To be filled]

#### Consequences
[To be analyzed]

#### Alternatives Considered
- Single-user: Simpler auth, faster development
- Multi-user from start: More complex, but no migration later
- Single-user with multi-user data model: Compromise approach

---

### [ADR-003] Processing Architecture: Real-time vs Batch
**Date**: 2025-08-03  
**Status**: Proposed  
**Deciders**: TBD  

#### Context
How should we process incoming emails for subscription detection?

#### Decision
[To be filled]

#### Consequences
[To be analyzed]

#### Alternatives Considered
- Real-time (webhooks): Immediate processing, more complex
- Batch (cron): Simpler, delayed insights
- Hybrid: Real-time receiving, batch processing

---

### [ADR-004] LLM Integration Approach
**Date**: 2025-08-03  
**Status**: Proposed  
**Deciders**: TBD  

#### Context
How to integrate LLM for subscription detection and classification?

#### Decision
[To be filled]

#### Consequences
[To be analyzed]

#### Alternatives Considered
- Direct API calls: Simple but potentially expensive
- Batch processing: Cost-effective but delayed
- Local LLM: Privacy-focused but requires resources
- Hybrid: Local for basic, API for complex

---

## Index by Category

### Architecture
- ADR-001: Email Storage Strategy
- ADR-002: User Architecture

### Processing
- ADR-003: Processing Architecture
- ADR-004: LLM Integration

### [More categories to be added as decisions are made]