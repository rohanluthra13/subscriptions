# Project Implementation Workflow

This document defines a two-phase workflow for implementing projects from the detailed workplan. This approach ensures human validation of key decisions while maintaining developer autonomy during implementation.

## Overview

Each project follows a two-phase approach:
1. **Analysis & Design Review** - Understand requirements, identify decisions, get approval
2. **Implementation** - Execute the approved plan autonomously

## Phase 1: Analysis & Design Review

### Prompt Template
```
Analyze project [PROJECT_NAME] from @docs/planning/detail_workplan.md

1. Review all deliverables and success criteria
2. Cross-reference with @docs/architecture/DESIGN.md for technical specs
3. Identify key decision points that need human input
4. Create implementation plan with:
   - File structure needed
   - Key technical choices (e.g., connection pooling approach)
   - Any gaps or ambiguities in the specs
   - Proposed solutions for each decision point

Present your analysis and wait for approval before proceeding.
```

### Expected Output
The agent should provide:
- Summary of deliverables
- Proposed file structure
- List of key decisions with recommendations
- Any clarification questions
- Rough implementation order

## Phase 2: Implementation

### Prompt Template
```
Implement the approved plan for [PROJECT_NAME]

**Key Documents:**
- Deliverables & Success Criteria: @docs/planning/detail_workplan.md
- Technical Specifications: @docs/architecture/DESIGN.md
- Architecture Decisions: @docs/architecture/decisions/

**Decision Guidelines:**
- Follow existing patterns from the codebase
- When choosing between options, prefer: simplicity > features > performance
- If a decision significantly changes the design, ask before proceeding
- For implementation details not specified, use your judgment

**Git Workflow:**
1. Create branch: feature/[project-id]-[project-name]
2. Commit after each major deliverable:
   - Use conventional commits (feat:, fix:, docs:, etc.)
   - Keep commits focused and atomic
   - Include brief description of what was implemented
3. Run lint/typecheck before final commit
4. Create PR only after ALL deliverables are complete and tested

**Definition of Done:**
- All deliverables implemented
- All success criteria met
- Code passes lint and typecheck
- Manual testing confirms functionality

Begin implementation. Ask only if you encounter blocking issues or need critical decisions that would change the architecture.
```

## Example: P2 Database Layer

### Phase 1 Analysis (Human Reviews)
```
Agent analyzes P2 and identifies:
- Need to choose between connection pooling libraries
- Clarification on encryption approach for tokens
- Proposed directory structure: src/lib/db/
- Recommends using Drizzle's built-in pooling

Human reviews and approves/modifies approach
```

### Phase 2 Implementation (Agent Executes)
```
Agent implements with commits:
- feat: setup Drizzle ORM configuration
- feat: implement database schema with all tables
- feat: create DatabaseService class with CRUD operations
- feat: add seed and migration scripts
- test: verify database operations
- docs: update setup instructions

Creates PR with summary of changes
```

## Benefits

1. **Reduced Rework** - Catch design issues before implementation
2. **Human Oversight** - Maintain control over architectural decisions
3. **Developer Autonomy** - Clear boundaries for independent work
4. **Clear Commits** - Easy to review and understand changes
5. **Quality Gates** - Built-in testing and linting requirements

## When to Use Each Phase

### Skip Phase 1 for:
- Simple, well-defined tasks
- Bug fixes
- Documentation updates
- Tasks with no architectural decisions

### Always Use Phase 1 for:
- New service implementations
- Database schema changes
- External API integrations
- Security-related features
- Any task with multiple valid approaches

## Workflow Variations

### Quick Implementation (Single Phase)
For simple, well-defined tasks:
```
Implement [SIMPLE_TASK] from [SOURCE]

Follow existing patterns. Commit when complete.
Run lint/typecheck before committing.
```

### Research Task
For investigation without implementation:
```
Research [TOPIC] in the codebase

1. Search for existing implementations
2. Review relevant documentation
3. Identify current patterns and approaches
4. Summarize findings with code references

No implementation needed - only provide analysis.
```

## Next Steps

1. Test this workflow with P2 (Database Layer)
2. Refine based on experience
3. Create project-specific templates as needed
4. Consider automating common patterns