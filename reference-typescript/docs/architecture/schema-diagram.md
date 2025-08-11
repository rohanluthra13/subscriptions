# Database Schema Diagram

## Entity Relationship Diagram

```mermaid
erDiagram
    users {
        text id PK
        text email UK
        text name
        timestamp created_at
        timestamp updated_at
    }

    connections {
        text id PK
        text user_id FK
        text email
        text access_token
        text refresh_token
        timestamp token_expiry
        text history_id
        timestamp last_sync_at
        boolean is_active
        boolean is_syncing
        int current_sync_phase
        timestamp created_at
        timestamp updated_at
    }

    subscriptions {
        text id PK
        text user_id FK
        text connection_id FK
        text vendor_name
        text vendor_email
        decimal amount
        text currency
        text billing_cycle
        date next_billing_date
        date last_billing_date
        date signup_date
        timestamp detected_at
        text status
        text renewal_type
        decimal confidence_score
        boolean user_verified
        text user_notes
        text category
        jsonb story_timeline
        text[] source_email_ids
        boolean needs_review
        timestamp created_at
        timestamp updated_at
    }

    processed_emails {
        text id PK
        text connection_id FK
        text gmail_message_id UK
        text gmail_thread_id
        text subject
        text sender
        timestamp received_at
        timestamp processed_at
        boolean is_subscription
        text subscription_id FK
        decimal confidence_score
        text processing_error
        timestamp fetched_at
        text vendor
        text email_type
        timestamp classified_at
    }

    sync_jobs {
        text id PK
        text connection_id FK
        text job_type
        text status
        int total_emails
        int processed_emails
        int subscriptions_found
        int errors_count
        timestamp started_at
        timestamp completed_at
        text error_message
    }

    %% Relationships
    users ||--o{ connections : "has"
    users ||--o{ subscriptions : "owns"
    connections ||--o{ subscriptions : "detects"
    connections ||--o{ processed_emails : "processes"
    connections ||--o{ sync_jobs : "runs"
    subscriptions ||--o{ processed_emails : "found_in"
```

## Table Details

### Core Tables

#### `users` Table
- **Purpose**: Multi-user foundation (single-user MVP implementation)
- **Key Fields**: 
  - `id`: Primary key (defaults to '1' for MVP)
  - `email`: User's email address
  - `name`: User's display name

#### `connections` Table  
- **Purpose**: Gmail OAuth connections and 5-phase pipeline tracking
- **Key Fields**:
  - `user_id`: Links to users table (defaults to '1')
  - `access_token`/`refresh_token`: Gmail API credentials
  - `history_id`: Gmail history ID for incremental sync
  - `last_sync_at`: Timestamp of last successful sync
  - **NEW:** `is_syncing`: Boolean flag for active pipeline execution
  - **NEW:** `current_sync_phase`: Tracks pipeline progress (1-5)

#### `subscriptions` Table
- **Purpose**: Final subscription records from Phase 5
- **Key Fields**:
  - `vendor_name`: Service provider name
  - `amount`/`currency`: Billing amount
  - `billing_cycle`: 'monthly', 'yearly', 'weekly', 'one-time'
  - `next_billing_date`/`last_billing_date`: Important dates
  - **NEW:** `signup_date`: When subscription started (from Phase 4 story)
  - `confidence_score`: LLM detection confidence (0.00-1.00)
  - `status`: 'active', 'inactive', 'paused', 'unknown'
  - `renewal_type`: 'auto_renew', 'manual_renew', 'cancelled', 'free_tier', 'unknown'
  - **NEW:** `story_timeline`: JSONB chronological events from Phase 4
  - **NEW:** `source_email_ids`: Array linking back to processed_emails
  - **NEW:** `needs_review`: Flag for manual user review

### Pipeline Tables

#### `processed_emails` Table
- **Purpose**: Track emails through all 5 phases of pipeline
- **Phase 1 Fields** (metadata):
  - `gmail_message_id`: Unique Gmail message identifier
  - `subject`: Email subject line
  - `sender`: Email sender address
  - `received_at`: When email was received
  - `fetched_at`: When metadata was fetched (Phase 1)
- **Phase 2 Fields** (classification):
  - `is_subscription`: Boolean from LLM classification (renamed from subscription_found)
  - `vendor`: Extracted vendor name (Phase 2 addition)
  - `email_type`: 'signup', 'billing', 'cancellation', etc. (Phase 2 addition)
  - `confidence_score`: LLM confidence score (existing field)
  - `classified_at`: When classification was completed (Phase 2 addition)
- **Final Fields**:
  - `subscription_id`: Links to final subscription (if created)
  - `processing_error`: Error message if processing failed

#### `sync_jobs` Table
- **Purpose**: Track 5-phase pipeline execution progress
- **Key Fields**:
  - `job_type`: 'phase1', 'phase2', 'complete_pipeline', 'manual_sync'
  - `status`: 'running', 'completed', 'failed', 'cancelled'
  - Progress counters: `total_emails`, `processed_emails`, `subscriptions_found`, `errors_count`

## Key Indexes

```sql
-- Performance indexes for common queries
CREATE INDEX idx_subscriptions_user_status ON subscriptions(user_id, status);
CREATE INDEX idx_subscriptions_next_billing ON subscriptions(next_billing_date) WHERE status = 'active';
CREATE INDEX idx_subscriptions_renewal_type ON subscriptions(renewal_type);
CREATE INDEX idx_processed_emails_connection ON processed_emails(connection_id, processed_at);
CREATE INDEX idx_processed_emails_gmail_id ON processed_emails(gmail_message_id);
CREATE INDEX idx_sync_jobs_status ON sync_jobs(status, started_at);
CREATE INDEX idx_connections_user_active ON connections(user_id, is_active);
```

## 5-Phase Pipeline Data Flow

1. **Phase 1 - Metadata**: `connections` → `processed_emails` (fetch email metadata)
2. **Phase 2 - Classification**: Update `processed_emails` with LLM results (subscription/vendor)
3. **Phase 3 - Grouping**: Group `processed_emails` by vendor_name (in-memory)
4. **Phase 4 - Story Building**: Analyze groups with LLM (in-memory)
5. **Phase 5 - Storage**: Create `subscriptions` records, link back to `processed_emails`

## 5-Phase Pipeline Tracking

- **Pipeline State**: `connections.is_syncing` and `connections.current_sync_phase`
- **Email Progress**: `processed_emails` tracks each email through phases
- **Job Monitoring**: `sync_jobs` provides overall progress and error handling
- **Final Results**: `subscriptions` contains story-enhanced subscription data

## Subscription Status Model

The subscription table uses a **two-field approach** to handle the complexity of real-world subscription states:

### Status Field (Access State)
- `active`: User currently has access to the service
- `inactive`: No current access (expired, cancelled, suspended)  
- `paused`: Temporarily paused (user-initiated or service-provided pause)
- `unknown`: LLM couldn't determine access state

### Renewal Type Field (Billing Behavior)
- `auto_renew`: Will automatically charge on next billing date
- `manual_renew`: Requires manual action to renew  
- `cancelled`: User cancelled, no future charges expected
- `free_tier`: Active service with no charges (free plan)
- `unknown`: Billing behavior unclear from emails

### Common Combinations
- **Active Netflix**: `status='active'`, `renewal_type='auto_renew'`
- **Free Spotify**: `status='active'`, `renewal_type='free_tier'`
- **Cancelled but still accessible**: `status='active'`, `renewal_type='cancelled'`
- **Expired subscription**: `status='inactive'`, `renewal_type='cancelled'`
- **Paused subscription**: `status='paused'`, `renewal_type='auto_renew'`

## MVP Implementation Notes

- **Single User**: All tables default to `user_id = '1'`
- **No Email Storage**: Email content never persisted, only metadata
- **Incremental Sync**: Uses `connections.history_id` and `last_sync_at`
- **Deduplication**: `processed_emails.gmail_message_id` prevents re-processing
- **Progress Tracking**: `sync_jobs` provides real-time sync status 