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