# Subscription Manager - Simple Gmail Speed Fix

## Current Problem
**Slow Gmail fetching**: 10,000 emails = 15+ hours (fetching full message bodies)  
**Solution**: Use Gmail API `format=MINIMAL` for metadata-only fetching

## Simple Implementation Plan

### Step 1: Add Fast Metadata Function
1. **Add new function** `fetch_metadata_only()` in main.py
   - Copy existing Gmail fetch logic
   - Add `?format=MINIMAL` to API calls  
   - Store in existing `processed_emails` table
   - No LLM classification

2. **Add test UI button**
   - "Fetch X emails metadata only" 
   - Test with 1000, 5000 emails
   - Verify speed improvement (should be 10x faster)

### Step 2: Test & Verify 
- **Expected**: 1000 emails in ~1-2 minutes (vs current ~20 minutes)
- **Database**: Same tables, just faster population
- **UI**: Progress logs show dramatic speed improvement

### Step 3: Clean Up
- Once fast metadata fetching confirmed working:
  - Remove old `sync_emails()` function
  - Remove old sync UI buttons
  - Keep only the fast metadata approach

## Success Criteria
- ✅ 1000 emails metadata in under 2 minutes
- ✅ Emails stored in existing database structure  
- ✅ No code complexity increase
- ✅ Single file architecture maintained

## Implementation Size
- **~50 lines of code changes**
- **1 new function**  
- **1 new UI button**
- **No new database tables**