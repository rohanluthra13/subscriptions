# Database Schema

SQLite database schema for the Subscription Manager application.

## Schema Diagram

```
┌─────────────────────────────────┐
│        connections              │
├─────────────────────────────────┤
│ id (TEXT) PK                    │
│ email (TEXT) UNIQUE             │
│ access_token (TEXT)             │
│ refresh_token (TEXT)            │
│ token_expiry (TIMESTAMP)        │
│ history_id (TEXT)               │
│ last_sync_at (TIMESTAMP)        │
│ is_active (BOOLEAN)             │
│ created_at (TIMESTAMP)          │
└─────────────────────────────────┘
             │
             │ connection_id (FK)
             ▼
┌─────────────────────────────────┐          ┌─────────────────────────────────┐
│      processed_emails           │          │        subscriptions            │
├─────────────────────────────────┤          ├─────────────────────────────────┤
│ id (TEXT) PK                    │          │ id (TEXT) PK                    │
│ connection_id (TEXT) FK         │          │ name (TEXT) UNIQUE              │
│ gmail_message_id (TEXT) UNIQUE  │          │ domains (TEXT/JSON)             │
│ subject (TEXT)                  │          │ category (TEXT)                 │
│ sender_email (TEXT)             │          │ cost (DECIMAL)                  │
│ sender_domain (TEXT) ───────────┼─────────▶│ currency (TEXT)                 │
│ sender_name (TEXT)              │  match   │ billing_cycle (TEXT)            │
│ received_at (TIMESTAMP)         │  domain  │ status (TEXT)                   │
│ subscription_id (TEXT) FK ──────┼─────────▶│ auto_renewing (BOOLEAN)         │
│ match_confidence (DECIMAL)      │          │ next_billing_date (DATE)        │
│ is_payment_receipt (BOOLEAN)    │          │ cancellation_date (DATE)        │
│ extracted_amount (DECIMAL)      │          │ notes (TEXT)                    │
│ processed_at (TIMESTAMP)        │          │ created_by (TEXT)               │
└─────────────────────────────────┘          │ created_at (TIMESTAMP)          │
                                              │ updated_at (TIMESTAMP)          │
                                              └─────────────────────────────────┘
                                                         ▲
                                                         │ subscription_id (FK)
                                                         │
                                              ┌──────────┴──────────────────────┐
                                              │         scratchpad              │
                                              ├─────────────────────────────────┤
                                              │ id (TEXT) PK                    │
                                              │ raw_text (TEXT)                 │
                                              │ parsed_name (TEXT)              │
                                              │ parsed_cost (DECIMAL)           │
                                              │ parsed_cycle (TEXT)             │
                                              │ subscription_id (TEXT) FK       │
                                              │ created_at (TIMESTAMP)          │
                                              └─────────────────────────────────┘
```

## Tables

### connections

| Column        | Type      | Constraints                        | Description                           |
|---------------|-----------|-----------------------------------|---------------------------------------|
| id            | TEXT      | PRIMARY KEY, DEFAULT randomblob   | Unique connection identifier          |
| email         | TEXT      | NOT NULL, UNIQUE                  | Connected Gmail account email         |
| access_token  | TEXT      | NOT NULL                          | OAuth 2.0 access token               |
| refresh_token | TEXT      | NOT NULL                          | OAuth 2.0 refresh token              |
| token_expiry  | TIMESTAMP | NOT NULL                          | When access token expires            |
| history_id    | TEXT      | -                                 | Gmail API history tracking           |
| last_sync_at  | TIMESTAMP | -                                 | Last email synchronization time      |
| is_active     | BOOLEAN   | DEFAULT 1                         | Whether connection is active          |
| created_at    | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP         | Connection creation timestamp         |

### processed_emails

| Column              | Type        | Constraints                           | Description                              |
|---------------------|-------------|---------------------------------------|------------------------------------------|
| id                  | TEXT        | PRIMARY KEY, DEFAULT randomblob       | Unique email record identifier           |
| connection_id       | TEXT        | NOT NULL                              | Link to Gmail connection                 |
| gmail_message_id    | TEXT        | UNIQUE NOT NULL                       | Gmail's unique message identifier        |
| subject             | TEXT        | -                                     | Email subject line                      |
| sender_email        | TEXT        | -                                     | Full sender email address               |
| sender_domain       | TEXT        | -                                     | Extracted domain from sender email      |
| sender_name         | TEXT        | -                                     | Display name of sender                  |
| received_at         | TIMESTAMP   | -                                     | When email was originally received       |
| subscription_id     | TEXT        | -                                     | Matched subscription (if identified)    |
| match_confidence    | DECIMAL(3,2)| -                                     | Confidence of subscription match (0-1)  |
| is_payment_receipt  | BOOLEAN     | DEFAULT 0                             | Whether email is a payment receipt      |
| extracted_amount    | DECIMAL(10,2)| -                                    | Payment amount extracted from email     |
| processed_at        | TIMESTAMP   | DEFAULT CURRENT_TIMESTAMP             | When record was created                  |

### subscriptions

| Column            | Type         | Constraints                        | Description                                      |
|-------------------|--------------|-----------------------------------|--------------------------------------------------|
| id                | TEXT         | PRIMARY KEY, DEFAULT randomblob   | Unique subscription identifier                   |
| name              | TEXT         | NOT NULL, UNIQUE                  | User-friendly name (e.g., "Netflix")             |
| domains           | TEXT         | -                                 | JSON array of domains ["netflix.com", "dvd.netflix.com"] |
| category          | TEXT         | -                                 | Category (streaming, productivity, etc)          |
| cost              | DECIMAL(10,2)| -                                 | Cost per billing cycle                          |
| currency          | TEXT         | DEFAULT 'USD'                     | Currency code (e.g., USD, EUR, GBP)             |
| billing_cycle     | TEXT         | -                                 | monthly/yearly/quarterly/one-time               |
| status            | TEXT         | DEFAULT 'active'                  | active/cancelled/trial/paused                   |
| auto_renewing     | BOOLEAN      | DEFAULT 1                         | Whether subscription auto-renews                |
| next_billing_date | DATE         | -                                 | Next expected charge date                       |
| cancellation_date | DATE         | -                                 | When subscription was/will be cancelled         |
| notes             | TEXT         | -                                 | Additional notes or information                 |
| created_by        | TEXT         | DEFAULT 'user'                    | Origin: user/gmail_import/llm                   |
| created_at        | TIMESTAMP    | DEFAULT CURRENT_TIMESTAMP         | When subscription was added                     |
| updated_at        | TIMESTAMP    | DEFAULT CURRENT_TIMESTAMP         | Last update timestamp                            |

### scratchpad

| Column          | Type      | Constraints                        | Description                              |
|-----------------|-----------|-----------------------------------|------------------------------------------|
| id              | TEXT      | PRIMARY KEY, DEFAULT randomblob   | Unique scratchpad item identifier        |
| raw_text        | TEXT      | NOT NULL                          | User-entered subscription info           |
| parsed_name     | TEXT      | -                                 | LLM-extracted subscription name          |
| parsed_cost     | DECIMAL(10,2) | -                             | LLM-extracted cost                      |
| parsed_cycle    | TEXT      | -                                 | LLM-extracted billing cycle             |
| subscription_id | TEXT      | -                                 | Link to created subscription (if converted) |
| created_at      | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP         | When item was added                      |

## Relationships

```
connections.id ←── processed_emails.connection_id
processed_emails.subscription_id ──→ subscriptions.id
processed_emails.sender_domain ←→ subscriptions.domains (JSON array match)
scratchpad.subscription_id ──→ subscriptions.id
```

## Key Design Principles

1. **Subscriptions are standalone**: They don't require email/domain to exist
2. **Name is the primary identifier**: Users refer to subscriptions by name
3. **Domains are optional**: Stored as JSON array for flexibility
4. **Emails provide evidence**: They support and validate subscriptions but aren't required

## Indexes

- UNIQUE(connections.email) - One connection per email account
- UNIQUE(subscriptions.name) - No duplicate subscription names
- UNIQUE(processed_emails.gmail_message_id) - Prevent duplicate email processing

## Storage

Database file: `subscriptions.db` (SQLite file in application root directory)

## Domain Storage Example

```sql
-- Single domain
domains: '["netflix.com"]'

-- Multiple domains  
domains: '["spotify.com", "support.spotify.com", "open.spotify.com"]'

-- No domain (manually added)
domains: NULL or '[]'
```

## JSON Operations

```sql
-- Check if email domain matches subscription
WHERE json_extract(subscriptions.domains, '$') LIKE '%' || processed_emails.sender_domain || '%'

-- Add a domain
UPDATE subscriptions 
SET domains = json_insert(domains, '$[#]', 'newdomain.com')

-- Get all domains for a subscription
SELECT json_each.value 
FROM subscriptions, json_each(subscriptions.domains)
WHERE subscriptions.name = 'Netflix'
```