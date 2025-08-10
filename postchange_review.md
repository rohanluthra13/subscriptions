# Post-Change Comprehensive Review Protocol

## Purpose
This protocol ensures that code changes, refactors, and deletions don't leave broken references or create runtime errors. It should be executed after any significant code modification.

## Instructions for AI Coding Agents

You have just performend a change, now perform this comprehensive impact analysis
The below points are guidelines, not prescriptive items. Please adapt your analysis to the specific change you're addressing.

### 1. Identify Changed Entities
- List all deleted, renamed, or significantly modified:
  - Files and directories
  - Functions, methods, and classes
  - API endpoints and routes
  - Components and modules
  - Database fields and tables
  - Environment variables and configuration keys
- Note their original names/paths and new names/paths (if renamed)

### 2. Smart Reference Search
For each changed entity, search for:
- **Direct references**: Exact name matches in code
- **Partial matches**: Substring of the name that might be composed
- **String literals**: API calls, dynamic imports, route definitions
- **Related patterns**: If you deleted "phase1", also search "phase2", "phase_1", "Phase1", etc.
- **Comments and documentation**: May contain outdated references
- **Configuration files**: JSON, YAML, TOML, .env files
- **Test files**: Often forgotten during refactors

### Common Patterns to Check
When searching for references, consider variations:
- **Pluralization**: user/users, item/items, component/components
- **Case variations**: getUserProfile, get-user-profile, get_user_profile
- **Partial paths**: '../phase1' might be referenced as just 'phase1'
- **Import/Export patterns**:
  - Default vs named imports (might be aliased)
  - Dynamic imports: `import('./oldFile')`
  - Lazy loading: `React.lazy(() => import('./oldComponent'))`

### 3. Dependency Analysis
Consider:
- **Upstream**: What calls this code?
- **Downstream**: What does this code call?
- **Parallel structures**: Similar code that might need the same change
- **Shared types/interfaces**: TypeScript types, GraphQL schemas, API contracts
- **Data flow**: Where does data from this code go?

### 4. Risk Assessment
For each reference found, evaluate:
- **Compile-time break?** ✅ Good - will be caught immediately
- **Runtime break?** ⚠️ Bad - need to fix before deployment
- **Silent failure?** 🚨 Critical - must fix (e.g., API calls that fail silently)
- **Test coverage?** Does a test catch this?
- **Production vs Development**: Is this reference in production code?

### 5. Report Issues
Create a prioritized list of findings:

```
CRITICAL (Silent Failures):
- [ ] Description of issue, file:line

HIGH (Runtime Breaks):
- [ ] Description of issue, file:line

MEDIUM (Test Breaks):
- [ ] Description of issue, file:line

LOW (Documentation/Comments):
- [ ] Description of issue, file:line
```

### 6. Validation Actions
After fixing issues:
- Run the build process
- Execute test suite
- Check for TypeScript errors
- Test critical user paths manually if needed

## What to Skip
Don't search in:
- `node_modules/`, `vendor/`, or other dependency directories
- `.next/`, `dist/`, `build/`, or other generated outputs
- `.git/` directory
- Binary files and images
- Lock files (package-lock.json, yarn.lock)

## Example Usage

**Scenario**: Deleted `/api/users/profile` endpoint and replaced with `/api/profile`

**Search executed**:
```bash
# Direct references
grep -r "users/profile" --exclude-dir=node_modules --exclude-dir=.next

# API calls
grep -r "fetch.*users/profile" --exclude-dir=node_modules
grep -r "axios.*users/profile" --exclude-dir=node_modules

# String construction
grep -r "users.*profile" --exclude-dir=node_modules

# Related endpoints
grep -r "users/settings" --exclude-dir=node_modules  # Might have similar pattern
```

**Issues found**:
```
CRITICAL:
- [ ] Frontend API call using string literal 'api/users/profile' - src/hooks/useProfile.ts:23

HIGH:
- [ ] API test expecting /users/profile endpoint - tests/api/profile.test.ts:45
```

## When to Use This Protocol

Always use after:
- Deleting files or directories
- Renaming functions, components, or endpoints
- Changing API contracts
- Modifying database schemas
- Refactoring import/export patterns
- Updating configuration structures


---

*This protocol helps catch integration issues that unit tests might miss and prevents the "everything builds but nothing works" syndrome.*