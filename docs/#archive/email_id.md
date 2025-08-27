# Email ID Migration Plan

## Problem
LLMs struggle with verbose Gmail message IDs in batch operations like `mark_emails_analyzed()`. Current Gmail IDs are long alphanumeric strings (16+ chars) making bulk operations cumbersome and exposing Google's internal identifiers.

## Solution
Replace Gmail message IDs with sequential integer IDs in MCP interface while maintaining internal Gmail ID mapping for API operations.

## Benefits
- **Efficiency**: `mark_emails_analyzed([1,2,3])` vs `mark_emails_analyzed(["18c5c9b3a4f2e8d1", ...])`  
- **Security**: Don't expose Google's internal message identifiers
- **Future potential**: Enable range operations `mark_analyzed(1, 100)` or batch shortcuts

## High-Level Implementation

### 1. Database Schema Changes
- Add auto-increment `id` PRIMARY KEY to `processed_emails` table
- Keep existing `gmail_message_id` column for internal Gmail API operations
- Update indexes to include new `id` column
- Migration script to assign sequential IDs to existing records

### 2. MCP Interface Updates
**Tools to modify:**
- `get_email_metadata()`: Return our `id` instead of `gmail_message_id`
- `mark_emails_analyzed()`: Accept our `id` list instead of Gmail IDs
- `get_email_content()`: Update to use our IDs in response

**No changes needed:**
- `fetch_email_content()`: Continues using Gmail IDs internally for API calls
- `fetch_email_metadata()`: Gmail sync operation, no ID exposure

**JSON format change:**
```json
// Current
{"emails": [{"id": "18c5c9b3a4f2e8d1", "subj": "...", ...}]}

// Proposed  
{"emails": [{"id": 1, "subj": "...", ...}]}
```

### 3. Simple SQL Updates
- `mark_emails_analyzed()`: Change WHERE clause from `gmail_message_id IN (?)` to `id IN (?)`
- No complex mapping layer needed - analysis workflow uses our IDs exclusively
- Gmail API operations remain unchanged

### 4. Testing Strategy
- Test with existing data (migration)
- Test new email processing preserves ID assignment
- Test all MCP tools work with new ID format
- Test Gmail API operations still function correctly
- Performance test with large ID lists

## Implementation Order
1. **Database migration**: Add ID column, populate existing records
2. **MCP interface**: Update 3 tools to use new IDs (simple changes)
3. **Testing**: Test analysis workflow with new IDs
4. **Documentation**: Update schema.md and tool descriptions

## Complexity Estimate
**Low-Medium** - Simple database schema addition and straightforward tool updates. No complex mapping needed since Gmail operations remain separate.

## Risks & Considerations
- ID stability: Ensure no gaps or reuse of IDs
- Migration complexity: Handle existing data gracefully
- Debugging: May occasionally need to trace back to Gmail IDs
- Rollback plan: Keep Gmail IDs for potential rollback