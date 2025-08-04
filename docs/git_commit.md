# Git Commit Workflow Prompt

## Purpose
This document provides a standardized prompt for requesting git commits across any project.

## The Prompt Template

```
commit these changes please
```

That's it! This simple prompt triggers a comprehensive commit workflow.

## What Happens When You Use This Prompt

1. **Status Check**: I'll run `git status` to see all changes
2. **Review Changes**: I'll check both staged and unstaged changes
3. **Recent History**: I'll look at recent commits to match the project's style
4. **Smart Staging**: I'll handle:
   - New files
   - Modified files
   - Deleted files
   - .gitignore compliance
   - Embedded repositories
5. **Commit Message**: I'll write a descriptive commit message following conventional commit format

## Key Information I Extract Automatically

### From Git Status
- What files were added/modified/deleted
- Current branch information
- Staging status

### From File Changes
- Type of changes (docs, feat, fix, refactor, etc.)
- Scope of changes
- Impact analysis

### From Recent Commits
- Project's commit message style
- Conventional commit usage
- Message length preferences

## Commit Message Format

I follow this structure:
```
<type>(<scope>): <subject>

<body>

<footer>
```

Where:
- **type**: feat, fix, docs, style, refactor, test, chore
- **scope**: optional, the area of change
- **subject**: brief description
- **body**: detailed explanation of what and why
- **footer**: includes my signature

## Optional Modifiers

You can add these to the basic prompt:

```
commit these changes please [with message: "your custom message"]
commit these changes please [type: fix]
commit these changes please [no-push]
commit these changes please [amend]
```

## What I WON'T Do Without Explicit Request

1. **Push to remote** - I only commit locally
2. **Force push** - Requires explicit permission
3. **Rebase** - Requires explicit instruction
4. **Change git config** - Never modify git configuration
5. **Commit secrets** - I'll warn if I detect potential secrets

## Error Handling

I automatically handle:
- Embedded git repositories
- Large files that should be in .gitignore
- Merge conflicts (I'll alert you)
- Uncommitted changes in submodules

## Best Practices I Follow

1. **Atomic Commits**: One logical change per commit
2. **Clear Messages**: Explain why, not just what
3. **No Breaking Changes**: Without explicit mention
4. **Clean History**: No merge commits unless necessary

## Project-Specific Patterns

I automatically detect and follow:
- Conventional commits (if used)
- Emoji usage (only if project uses them)
- Issue linking patterns
- Sign-off requirements

---

*Note: This workflow is designed to be project-agnostic and will adapt to your project's conventions automatically.*