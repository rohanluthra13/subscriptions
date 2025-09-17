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

### Form Generation Code Duplication
**Issue**: Static form template in manage.html duplicated in server-side form generation
**Details**: `_generate_subscription_form_html()` (main.py:1240-1406) creates 180+ lines of HTML that duplicates the static modal form template (manage.html:20-139)
**Impact**: Maintenance burden - form changes require updates in two places, risk of inconsistency
**Effort**: High - requires template fragment system or server-side template includes

### Long Function Complexity
**Issue**: Several functions exceed single responsibility principle
**Details**: `openModal()` (61 lines), `_generate_subscription_form_html()` (166 lines), `fetch_year_of_emails()` (189 lines)
**Impact**: Reduced readability and maintainability, harder to test individual components
**Effort**: Medium - break down into smaller, focused functions

### Magic Numbers and Configuration
**Issue**: Hardcoded values throughout codebase without configuration constants
**Details**: Timeout values (15000ms), batch sizes (10), retry waits (2**(attempt+1)), rate limits
**Impact**: Difficult to tune performance, unclear business rules, harder to test with different values
**Effort**: Low - extract to configuration file or constants

### Manual HTML String Building
**Issue**: HTML generation uses string concatenation instead of template system
**Details**: Multiple instances in main.py (lines 710-732, 1240-1406) build HTML with f-strings
**Impact**: Security risk (manual escaping required), poor maintainability, harder to preview layouts
**Effort**: High - requires template system with proper escaping and includes

### Client-Side State Management Complexity
**Issue**: Extensive DOM caching and form field management in JavaScript
**Details**: 10+ cached form field variables, manual re-caching after DOM updates, complex initialization
**Impact**: Not fully aligned with HTML-over-wire principles, potential memory leaks, fragile to DOM changes
**Effort**: Medium - further simplify client-side logic, rely more on server-rendered state

### HTTP Method Inconsistency
**Issue**: No consistent REST-like structure across API endpoints
**Details**: Mix of POST endpoints, custom paths, and URL parameters without clear pattern
**Impact**: Harder API to understand and maintain
**Effort**: High - would require API redesign and frontend updates

---

## Process Notes
- Items added during HTML-over-wire refactor Phase 1 review (2025-09-16)
- Updated after Phase 2 completion and technical debt analysis (2025-09-17)
- Modal State Persistence issue resolved through HTML-over-wire Phase 2 implementation
- Unused Variables & Dead Code partially addressed in technical debt cleanup commit
- Prioritize based on impact vs. effort when planning cleanup sprints
- Remove items when addressed and document resolution in changelog

## Recently Resolved (2025-09-17)
- **Event Handling Inconsistency**: Standardized to event delegation pattern throughout
- **Modal State Persistence**: Resolved through server-rendered forms in HTML-over-wire Phase 2
- **Dead Code Comments**: Removed obsolete REMOVED: comments and unused variables