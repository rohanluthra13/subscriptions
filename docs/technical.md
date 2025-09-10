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

## Dependencies
What we need (MCP SDK, etc.)