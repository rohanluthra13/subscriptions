# Category Database Implementation Brief

**Date**: 2025-09-09  
**Session Focus**: Database schema enhancement for category management  
**Agent Task**: Implement proper category management system with database table

## Current State

### Form Enhancements Completed ✅
- Added category and status dropdowns to subscription form modal (`templates/views/manage.html`)
- Fixed critical dropdown reliability issues (event delegation, race conditions, duplicate listeners)
- Form now includes: name, cost row (amount/cycle/currency), category, status, website, notes
- All dropdown functionality working reliably after debugging session

### Database Schema Status
- `subscriptions.category TEXT` - exists, stores free text, no constraints
- Categories currently hardcoded in HTML: `streaming`, `software`, `news`, `productivity`, `entertainment`, `education`, `other`
- No category management system - options fixed in frontend code

## Task: Implement Categories Table

### Database Changes Needed
```sql
CREATE TABLE IF NOT EXISTS categories (
    name TEXT PRIMARY KEY,
    is_standard BOOLEAN DEFAULT 0,
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Implementation Requirements
1. **Schema Update** - Add categories table creation to `main.py` database initialization
2. **Data Population** - Insert standard categories on first run with `is_standard=1`
3. **API Endpoints** - Create methods to get/add categories in `SubscriptionManager` class
4. **UI Integration** - Update dropdown to load from database instead of hardcoded HTML
5. **Hybrid Approach** - Allow both database categories AND custom text input

### Key Files to Modify
- `main.py` - Add table creation, API methods for category CRUD
- `templates/views/manage.html` - Update dropdown to load from server-side data
- `docs/schema.md` - Document new categories table

### Design Decisions Made
- **Keep existing TEXT field** - No migration of `subscriptions.category`, maintain backward compatibility  
- **Database over resources** - Categories table instead of `resources/categories.md` for app deployment compatibility
- **Usage tracking** - Track category usage for analytics/suggestions
- **Standard vs custom** - Flag to distinguish predefined vs user-created categories

### Technical Context
- App uses "HTML Over The Wire" architecture - server renders dropdown options
- Event delegation pattern implemented for dropdowns (avoid re-initialization issues)
- MCP server (`mcp_server.py`) will access categories via database connection

## Success Criteria
- Categories loaded from database in dropdown
- Users can select existing categories or enter custom text
- Standard categories populated automatically
- No breaking changes to existing subscription data
- Category usage tracked for future enhancements

## Current Architecture Pattern
Follow existing patterns in `main.py`:
- Use `@handle_db_errors` decorator for database methods
- Add methods to `SubscriptionManager` class
- Template rendering via `get_manage_content()` method
- Maintain single-file architecture principle