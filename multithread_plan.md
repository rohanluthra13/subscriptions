# Multi-Threading Implementation Plan

## Problem Statement
The HTTP server in `main.py` is single-threaded, causing it to become unresponsive during long-running operations like email fetching (10-15 minutes). This prevents the MCP server from checking status or triggering operations while an email fetch is in progress.

## Solution Overview
Implement multi-threading to keep the HTTP server responsive while processing long operations in the background.

## Status Summary
✅ **Steps 1-2 COMPLETED** - Core functionality working  
🔄 **Steps 3-4 FOR LATER** - Optional enhancements (job monitoring, cleanup)

**Current capabilities:** Background jobs eliminate timeouts, progress visible in terminal  
**Missing capabilities:** Cannot check job status via API, jobs accumulate in memory

## Implementation Steps

### Step 1: Make HTTP Server Multi-Threaded (5 minutes) ✅ COMPLETED
**Goal:** Allow the server to handle multiple requests simultaneously

**Changes:**
- Replace basic `HTTPServer` with `ThreadedHTTPServer` 
- Use `ThreadingMixIn` to add threading capability
- No changes to request handlers needed

**Testing:**
- Start email fetch via web UI
- While fetch is running, verify `/status` endpoint responds
- Confirm MCP `get_email_status` tool works during fetch

**Success Criteria:**
- HTTP endpoints respond during email fetch
- No server timeouts from MCP tools

---

### Step 2: Basic Background Jobs (15 minutes) ✅ COMPLETED
**Goal:** Move email fetch to background thread with job tracking

**Changes:**
- Create `BackgroundJob` class to track job state
- Store active jobs in a dictionary (job_id → job_info)
- Modify `api_fetch_emails()` to start background thread
- Return job ID immediately instead of waiting

**New Data Structure:**
```
jobs = {
    "job_123": {
        "id": "job_123",
        "type": "email_fetch",
        "status": "running",
        "started_at": timestamp,
        "result": None,
        "error": None
    }
}
```

**Testing:**
- Trigger email fetch via MCP tool
- Verify immediate response with job ID
- Check job exists in tracking system

**Success Criteria:**
- Email fetch returns immediately with job ID
- Background thread executes fetch successfully
- Job tracking system maintains job state

---

### Step 3: Job Status Tracking (15 minutes) 🔄 FOR LATER
**Goal:** Add endpoints to check job progress and results

**New Endpoints:**
- `GET /api/jobs` - List all jobs
- `GET /api/jobs/{job_id}` - Get specific job status

**Job Progress Tracking:**
- Add progress fields to job object:
  - `current_batch`: Current batch number
  - `total_batches`: Total number of batches
  - `emails_processed`: Count of emails processed
  - `time_elapsed`: Seconds since start

**Changes to Email Fetch:**
- Update job progress during processing
- Instead of `print()`, update job object
- Capture final results in job object

**Testing:**
- Start email fetch
- Poll job status endpoint during processing
- Verify progress updates in real-time
- Check final results after completion

**Success Criteria:**
- Job status endpoint returns current progress
- Progress updates during fetch operation
- Final results available when complete

---

### Step 4: Enhanced Progress & Cleanup (10 minutes) 🔄 FOR LATER
**Goal:** Polish the system with better progress reporting and resource management

**Enhancements:**
- Add estimated time remaining to progress
- Include detailed batch information
- Add percentage complete calculation

**Job Cleanup:**
- Auto-delete completed jobs after 1 hour
- Limit to 10 most recent jobs
- Add cleanup thread or timer

**MCP Tool Updates:**
- Update `trigger_email_fetch` to return job ID
- Enhance `get_email_status` to check for active jobs
- Add progress information to status response

**Error Handling:**
- Capture exceptions in background thread
- Store error details in job object
- Return error status in job endpoint

**Testing:**
- Run multiple fetches to test job limit
- Verify old jobs are cleaned up
- Test error scenarios (network failure, auth expiry)

**Success Criteria:**
- Jobs auto-cleanup after timeout
- Memory usage stays bounded
- MCP tools provide useful progress feedback
- Errors are properly captured and reported

---

## Alternative: Simple Timeout Increase
If the above seems too complex, a simpler workaround:
- Increase MCP timeout from 1 second to 30 seconds
- Accept that server is blocked during fetch
- No code changes to threading model

## Benefits of Full Implementation
- HTTP server always responsive
- Multiple operations can run concurrently
- Better user experience with progress tracking
- Foundation for future desktop app
- Professional-grade job management

## Risks & Considerations
- Thread safety for database access (SQLite handles this well)
- Increased code complexity
- Potential for threading bugs
- Need to test concurrent operations carefully

## Decision Point
Start with Step 1 only - this might solve the immediate problem with minimal risk. Only proceed to Steps 2-4 if needed for better user experience or if Step 1 proves insufficient.