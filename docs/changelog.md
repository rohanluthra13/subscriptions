# Changelog

All notable changes to this project will be documented in this file.

## Entry Guidelines

- **Keep it concise**: Focus on user-facing changes and high-level architectural decisions
- **Avoid implementation details**: Function names, line counts, and file paths belong in commit messages
- **Structure**: Use Added/Changed/Fixed/Security sections as appropriate
- **Technical debt**: Document separately in `docs/technical-debt.md` rather than changelog
- **Target audience**: Developers who need to understand what changed, not how it was implemented

## [2025-09-17] - HTML-Over-Wire Refactor: Phase 2 Complete + Bug Fixes - CHANGED TO PARTIALLY COMPLETE ON RE-REVIEW. LIVE PLAN DOCUMENTS ADJUSTED. THIS ENTRY BELOW HAS INACCURACIES.

### Added
- Server-rendered subscription forms with populated data and dropdowns
- New form endpoints that return complete HTML instead of requiring client-side population
- Event delegation pattern for all modal and form interactions

### Changed
- Modal forms now load complete HTML from server instead of fetching JSON data
- Form submissions return HTML fragments for seamless updates without page reloads
- CRUD operations (create, update, delete) now follow HTML-over-wire architecture
- Eliminated ~400 lines of client-side form and dropdown JavaScript complexity

### Fixed
- Modal delete button functionality restored after Phase 1 changes
- Modal close button (X) now works correctly with server-rendered content
- Floating form labels properly hide/show when typing in fields
- Event handling standardized across all interactive elements

### Notes
- HTML-over-wire architecture now fully implemented for core subscription management
- Modal functionality completely restored and improved over pre-refactor state
- Server owns all presentation logic, client handles only UI interactions
- Application maintains full functionality while achieving architectural goals

## [2025-09-17] - HTML-Over-Wire Refactor: Phase 1 Step 3

### Changed
- Removed client-side data caching from manage view (Phase 1, Item 3)
- Modal population now fetches data from server instead of JavaScript cache
- Delete confirmations get subscription name from DOM instead of cache

### Added
- New `/api/subscriptions/{id}` endpoint for individual subscription retrieval
- `get_subscription_by_id()` method in SubscriptionManager class

### Notes
- Eliminates client-server state synchronization complexity
- Sets foundation for eventual modal-to-page conversion
- Server now single source of truth for all subscription data

## [2025-09-17] - Architecture Simplification: Feature Removal

### Removed
- Review feature (LLM analysis and user confirmation workflow)
- Notepad feature (user notes and brainstorming interface)
- Related UI navigation items and backend endpoints

### Changed
- Application now focused solely on Gmail integration and subscription management
- MCP server prompts updated to use direct subscription management instead of review workflow
- Documentation updated to reflect current three-view architecture (home, manage, emails)

### Fixed
- Cleaned up technical debt from removed features
- Eliminated dead code references and documentation inconsistencies

### Notes
- Net reduction of 617 lines of code while maintaining core functionality
- HTML-over-wire refactor scope reduced by 30% with cleaner foundation
- Preserves all Gmail OAuth, email processing, and subscription CRUD capabilities

## [2025-09-16] - HTML-Over-Wire Refactor: Phase 1 Step 1

### Changed
- Removed dynamic DOM generation in favor of server-rendered content
- Migrated notepad "+" button functionality to server-side endpoint
- Eliminated code duplication in subscription card and notepad item rendering

### Security
- Fixed XSS vulnerabilities in user input handling throughout notepad and subscription features

### Notes
- Maintains full functional compatibility while following HTML-over-wire architecture principles
- All changes preserve existing user experience
- Technical debt review identified pre-existing issues: error response inconsistency, template security architecture, unused variables, and modal state persistence problems 