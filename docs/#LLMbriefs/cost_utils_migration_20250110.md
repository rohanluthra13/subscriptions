# Cost Utilities Migration & Tech Debt - Session Brief

## Context
Extracting utility modules from main.py (2,327 lines) to improve maintainability while preserving agent-first architecture. Focus on cost utilities and currency handling.

## Current State

### Successfully Extracted Modules
- **utils/cost.py** - CostUtils class with Decimal precision, international currency support
- **utils/favicon.py** - Logo fetching utilities (created but not yet migrated)
- **utils/decorators.py** - Database error handling (created but not yet migrated)
- **database/schema.py** - Database initialization (created but not yet migrated)

### Migrated to Production
- ✅ **CostUtils** - Imported in main.py line 24, old class removed (was lines 205-271)

## Task Progress

### Completed
1. **Module Extraction**
   - Fixed critical issues: database row_factory, favicon memory leaks, Decimal precision
   - Enhanced CostUtils with international currency parsing, thousands separators

2. **Currency Standardization**
   - Database schema: USD → NZD default
   - MCP server: USD → NZD default  
   - All 6 subscription records now use NZD
   - Documentation updated to reflect NZD default

3. **Technical Debt Fixed**
   - Replaced hardcoded `${monthly_total:.2f}` formatting with CostUtils.format_cost_for_display()
   - No remaining hardcoded cost formatting in application

### Remaining Tech Debt

1. **Client-Side Cost Cleaning** (templates/views/manage.html:1165)
   ```javascript
   costValue = costValue.replace('$', '');  // Only handles $, not €, £, ¥
   ```

2. **MCP Server Integration** (mcp_server.py) - ✅ **COMPLETED**
   - ~~Still uses float operations instead of CostUtils~~
   - ~~No Decimal precision for financial calculations~~
   - **Fixed**: Now imports CostUtils and uses Decimal precision for billing calculations

3. **Currency Symbol Display** (utils/cost.py:86)
   ```python
   return f"${cost_decimal:.2f}"  // Always shows $ regardless of currency
   ```

4. **No Currency Symbol Mapping**
   - System stores NZD, EUR, GBP but can't display €, £ symbols

## Key Files Modified
- main.py - Imported CostUtils, removed old class
- mcp_server.py - Changed currency default to NZD
- database/schema.py - Changed schema default to NZD
- docs/schema.md - Updated documentation

## Next Steps
1. Fix client-side cost cleaning - use server-side CostUtils
2. ~~Integrate CostUtils into MCP server for precision~~ ✅ **COMPLETED**
3. Add currency → symbol mapping dictionary
4. Update display formatting to use correct currency symbols

## Testing Notes
- Run `python utils/cost.py` to test enhanced features
- Verify costs display correctly at http://localhost:8000
- Check home view totals and manage view subscription cards

## Environment
- Run in virtual environment: `source venv/bin/activate && python main.py`
- Database: subscriptions.db (SQLite)
- All currency defaults now standardized to NZD