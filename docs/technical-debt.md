# Technical Debt Registry

This document tracks known code quality issues, architectural inconsistencies, and improvement opportunities that don't break current functionality but should be addressed when time permits.

## Criteria for Inclusion
- Non-breaking improvements that require design decisions or broader refactoring
- Code quality issues that aren't immediately actionable
- Architectural inconsistencies discovered during feature development
- Performance or maintainability improvements that need investigation

## Current Items

### Error Response Inconsistency
**Issue**: Mixed error handling patterns across endpoints
**Details**: Some use `send_json_response({"success": False})`, others use `send_error(500, message)`
**Impact**: Inconsistent frontend error handling, confusing developer experience
**Effort**: Medium - requires standardizing error response format across all endpoints

### Template Security Architecture
**Issue**: Manual HTML escaping required at each call site
**Details**: Comment at main.py:721-723 indicates security responsibility pushed to developers
**Impact**: Risk of XSS vulnerabilities in future code, cognitive overhead
**Effort**: High - would require template system redesign with default escaping

### Unused Variables & Dead Code
**Issue**: Multiple unused variables throughout codebase
**Details**: `website_url_updated`, `subject`, `sender`, `sender_domain`, `received_at` in various functions
**Impact**: Code bloat, misleading variable names, potential confusion
**Effort**: Low - safe to remove after verification

### Mixed HTML Generation Patterns
**Issue**: Inconsistent formatting and structure in HTML generation code
**Details**: Some use multi-line f-strings with indentation, others use single-line strings
**Impact**: Reduced code readability and maintainability
**Effort**: Medium - establish and apply consistent formatting standards

### Modal State Persistence
**Issue**: Modals don't refresh data after CRUD operations without page reload
**Details**: `embedded_subscriptions` JavaScript data becomes stale after updates
**Impact**: User experience issue - edit forms appear blank until page refresh
**Effort**: Medium - requires client-side data synchronization or full HTML-over-wire migration

### HTTP Method Inconsistency
**Issue**: No consistent REST-like structure across API endpoints
**Details**: Mix of POST endpoints, custom paths, and URL parameters without clear pattern
**Impact**: Harder API to understand and maintain
**Effort**: High - would require API redesign and frontend updates

---

## Process Notes
- Items added during HTML-over-wire refactor Phase 1 review (2025-09-16)
- Prioritize based on impact vs. effort when planning cleanup sprints
- Remove items when addressed and document resolution in changelog