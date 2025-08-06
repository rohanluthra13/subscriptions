# API Usage Examples

## Authentication

All API endpoints (except OAuth callback) require authentication via API key:

```bash
# Header method (recommended)
curl -H "X-API-Key: your-api-key-123" http://localhost:3000/api/subscriptions

# Query parameter method
curl "http://localhost:3000/api/subscriptions?api_key=your-api-key-123"
```

## Gmail Connection Flow

### 1. Initiate OAuth Flow

```bash
curl -X POST \
  -H "X-API-Key: your-api-key-123" \
  -H "Content-Type: application/json" \
  -d '{"redirect_uri": "http://localhost:3000/dashboard"}' \
  http://localhost:3000/api/connections/gmail
```

Response:
```json
{
  "data": {
    "auth_url": "https://accounts.google.com/oauth/authorize?...",
    "state": "random-csrf-token"
  },
  "message": "Gmail authorization URL generated"
}
```

### 2. User Completes OAuth

User visits the `auth_url` and grants permissions. Google redirects to:
```
http://localhost:3000/api/connections/gmail/callback?code=xyz&state=random-csrf-token
```

The callback endpoint automatically processes the OAuth response and redirects to the dashboard.

## Sync Management

### Manual Sync

```bash
curl -X POST \
  -H "X-API-Key: your-api-key-123" \
  -H "Content-Type: application/json" \
  -d '{}' \
  http://localhost:3000/api/sync/manual
```

Response:
```json
{
  "data": {
    "job_id": "job_123",
    "status": "started",
    "message": "Manual sync started - checking for new emails since last sync"
  },
  "message": "Manual sync initiated"
}
```

### Check Sync Status

```bash
curl -H "X-API-Key: your-api-key-123" \
  http://localhost:3000/api/sync/status
```

Response:
```json
{
  "data": {
    "is_syncing": true,
    "current_job": {
      "job_id": "job_123",
      "job_type": "manual_sync",
      "started_at": "2025-08-06T10:30:00.000Z"
    },
    "last_sync_at": "2025-08-05T06:00:00.000Z",
    "next_scheduled_sync": "2025-08-07T06:00:00.000Z"
  }
}
```

### Monitor Job Progress

#### Regular Status Check
```bash
curl -H "X-API-Key: your-api-key-123" \
  http://localhost:3000/api/sync/jobs/job_123
```

Response:
```json
{
  "data": {
    "id": "job_123",
    "job_type": "manual_sync",
    "status": "running",
    "progress": {
      "total_emails": 150,
      "processed_emails": 75,
      "subscriptions_found": 3,
      "errors_count": 1
    },
    "started_at": "2025-08-06T10:30:00.000Z"
  }
}
```

#### Real-time Progress (SSE)
```bash
curl -H "X-API-Key: your-api-key-123" \
  -H "Accept: text/event-stream" \
  http://localhost:3000/api/sync/jobs/job_123
```

Response (SSE stream):
```
event: connected
data: {"connected": true, "jobId": "job_123"}

event: progress
data: {"total_emails": 150, "processed_emails": 25, "subscriptions_found": 1}

event: progress
data: {"total_emails": 150, "processed_emails": 50, "subscriptions_found": 2}

event: complete
data: {"jobId": "job_123", "stats": {"processed": 150, "subscriptionsFound": 3}, "message": "Sync completed. Found 3 new subscriptions."}
```

## Subscription Management

### List Subscriptions

```bash
curl -H "X-API-Key: your-api-key-123" \
  "http://localhost:3000/api/subscriptions?status=active&sort=amount&order=desc&limit=10"
```

Response:
```json
{
  "data": {
    "subscriptions": [
      {
        "id": "sub_123",
        "vendor_name": "Netflix",
        "vendor_email": "billing@netflix.com",
        "amount": "15.99",
        "currency": "USD",
        "billing_cycle": "monthly",
        "status": "active",
        "renewal_type": "auto_renew",
        "next_billing_date": "2025-08-15",
        "category": "streaming",
        "confidence_score": "0.95",
        "user_verified": false,
        "detected_at": "2025-08-06T10:00:00.000Z"
      }
    ],
    "total": 12,
    "summary": {
      "total_monthly": 89.97,
      "total_yearly": 120.00,
      "active_count": 12
    }
  }
}
```

### Update Subscription

```bash
curl -X PUT \
  -H "X-API-Key: your-api-key-123" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "cancelled",
    "user_notes": "Cancelled due to lack of use",
    "user_verified": true
  }' \
  http://localhost:3000/api/subscriptions/sub_123
```

### Delete Subscription

```bash
curl -X DELETE \
  -H "X-API-Key: your-api-key-123" \
  http://localhost:3000/api/subscriptions/sub_123
```

Response: `204 No Content`

## Data Export

### Export as CSV

```bash
curl -H "X-API-Key: your-api-key-123" \
  "http://localhost:3000/api/export?format=csv&status=active" \
  --output subscriptions.csv
```

### Export as JSON

```bash
curl -H "X-API-Key: your-api-key-123" \
  "http://localhost:3000/api/export?format=json" \
  --output subscriptions.json
```

## Error Handling

All endpoints return consistent error format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": {
      "errors": [
        {
          "path": ["amount"],
          "message": "Amount must be a positive number"
        }
      ]
    }
  }
}
```

### Common Error Codes

- `UNAUTHORIZED` (401): Invalid or missing API key
- `VALIDATION_ERROR` (400): Request validation failed
- `RATE_LIMIT_EXCEEDED` (429): Rate limit exceeded
- `CONNECTION_NOT_FOUND` (404): Gmail connection not found
- `SUBSCRIPTION_NOT_FOUND` (404): Subscription not found
- `SYNC_IN_PROGRESS` (409): Sync already running
- `GMAIL_API_ERROR` (500): Gmail API error
- `INTERNAL_ERROR` (500): Unexpected server error

## Rate Limits

- **General endpoints**: 100 requests per minute
- **Sync endpoints**: 10 requests per minute

Rate limit information is included in response headers when limits are approached.