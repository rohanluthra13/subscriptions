# Technical Approach

## Current Architecture
What we have now (Gmail ingestion, SQLite, web UI)

## MCP Architecture  
How it changes with MCP integration

## Data Preservation
What stays, what changes from current work

## Implementation Phases
High-level steps to get there

## Technical Decisions

### Data handling standards/mapping (2025-09-10)

**Decision**: Two-tier mapping approach with tier 1 universal rules and tier 2 business logic exceptions

**Mappings**: 

**Tier 1: Universal Rules (Standard Flow)**
- SQLite INTEGER (boolean) → JSON boolean → JS boolean
- SQLite REAL → JSON number → JS number  
- SQLite TEXT → JSON string → JS string
- SQLite BLOB → Base64 string → JS string (with metadata)
- SQLite NULL → JSON null → JS null

**Tier 2: Field-Specific Exceptions (Business Logic)**
- `cost` (REAL) → JSON string → JS string → parseFloat() *[precision preservation]*
- `timestamps` (TEXT) → JSON string (ISO) → JS Date() *[timezone consistency]*
- `domains` (TEXT array) → JSON string array → JS Array *[SQLite limitation workaround]*

**Rationale**: Eliminates conversion inconsistencies causing UI bugs (e.g., boolean 0/1 → true/false). Universal rules handle 90% of cases, exceptions preserve business logic requirements without compromising data integrity.

**Implementation**: Utility class pattern with centralized type handling, following existing CostUtils precedent.

### N+1 Query Pattern in Email Processing (2025-09-08)

**Decision**: Keep current implementation, downgrade from critical to monitoring

**Analysis Summary**:
- **Pattern exists**: Individual database queries in loop (classic N+1) at main.py:443
- **Performance acceptable**: 1000-2000 emails process "very fast" due to database indexing
- **Database optimization**: Unique constraint on `gmail_message_id` creates automatic index
- **SQLite efficiency**: O(log n) lookups prevent exponential slowdown
- **User experience**: No performance complaints with realistic email volumes

**Monitoring approach**:
- Watch for processing times >30 seconds for large email batches
- Consider batch optimization only if users report slowdowns
- Current indexes sufficient for typical usage (1K-5K emails annually)

**Conclusion**: Theoretical performance concern doesn't manifest in practice - focus optimization efforts elsewhere

### Modal UX + AJAX Architecture Decision (2025-09-18)

**Decision**: Maintain current modal-based AJAX approach as optimal HTML-over-wire implementation

**Context**: HTML-over-wire refactor planning questioned whether 436 lines of JavaScript and 6 AJAX calls conflicted with architectural goals.

**Analysis**:
- AJAX calls fetch HTML fragments (not JSON), following HTML-over-wire principles
- Modal UX inherently requires async form submission (cannot use standard POSTs in overlays)
- 436 lines breakdown: 260 lines UI/navigation, 176 lines form handling (zero business logic)
- Architecture provides modern UX while maintaining server-side business logic

**Alternative considered**: Page-based forms with standard POSTs
- Would eliminate ~200 lines of JavaScript
- Requires separate edit pages: `/manage` → `/edit/123` → `/manage`
- Less polished UX with full page reloads

**Rationale**: Current approach balances HTML-over-wire principles with modern user experience. The JavaScript is justified infrastructure for modal workflows, not unnecessary complexity.

## Dependencies
What we need (MCP SDK, etc.)