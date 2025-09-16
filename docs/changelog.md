# Changelog

All notable changes to this project will be documented in this file.

## Entry Guidelines

- **Keep it concise**: Focus on user-facing changes and high-level architectural decisions
- **Avoid implementation details**: Function names, line counts, and file paths belong in commit messages
- **Structure**: Use Added/Changed/Fixed/Security sections as appropriate
- **Technical debt**: Document separately in `docs/technical-debt.md` rather than changelog
- **Target audience**: Developers who need to understand what changed, not how it was implemented

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
- Technical debt review identified pre-existing issues: error response inconsistency, template security architecture, unused variables, and modal state persistence problems (see future cleanup opportunities)