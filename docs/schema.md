# Database Schema

SQLite database schema for the Subscription Manager application.

## Schema Diagram (Actual Implementation)

```
┌─────────────────────────────────┐
│        connections              │
├─────────────────────────────────┤
│ id (TEXT) PK                    │
│ email (TEXT) UNIQUE             │
│ access_token (TEXT)             │
│ refresh_token (TEXT)            │
│ token_expiry (TIMESTAMP)        │
│ last_sync_at (TIMESTAMP)        │
│ is_active (BOOLEAN)             │
│ created_at (TIMESTAMP)          │
└─────────────────────────────────┘

┌─────────────────────────────────┐          ┌─────────────────────────────────┐
│      processed_emails           │          │        subscriptions            │
├─────────────────────────────────┤          ├─────────────────────────────────┤
│ id (TEXT) PK                    │          │ id (TEXT) PK                    │
│ email (TEXT)                    │          │ name (TEXT) UNIQUE              │
│ gmail_message_id (TEXT) UNIQUE  │          │ domains (TEXT/JSON)             │
│ subject (TEXT)                  │          │ category (TEXT)                 │
│ sender (TEXT)                   │          │ cost (DECIMAL)                  │
│ sender_domain (TEXT)            │          │ currency (TEXT)                 │
│ received_at (TIMESTAMP)         │          │ billing_cycle (TEXT)            │
│ processed_at (TIMESTAMP)        │          │ status (TEXT)                   │
│ content (TEXT)                  │          │ auto_renewing (BOOLEAN)         │
│ content_fetched (BOOLEAN)       │          │ next_billing_date (DATE)        │
└─────────────────────────────────┘          │ notes (TEXT)                    │
                                              │ next_billing_date (DATE)        │
                                              │ notes (TEXT)                    │
                                              │ created_by (TEXT)               │
                                              │ created_at (TIMESTAMP)          │
                                              │ updated_at (TIMESTAMP)          │
                                              └─────────────────────────────────┘

┌─────────────────────────────────┐
│         scratchpad              │
├─────────────────────────────────┤
│ id (TEXT) PK                    │
│ item (TEXT)                     │
│ processed (BOOLEAN)             │
│ created_at (TIMESTAMP)          │
└─────────────────────────────────┘
```

Note: Tables are independent - no formal foreign key relationships implemented

## Tables

### connections

| Column        | Type      | Constraints                        | Description                           |
|---------------|-----------|-----------------------------------|---------------------------------------|
| id            | TEXT      | PRIMARY KEY, DEFAULT randomblob   | Unique connection identifier          |
| email         | TEXT      | NOT NULL, UNIQUE                  | Connected Gmail account email         |
| access_token  | TEXT      | NOT NULL                          | OAuth 2.0 access token               |
| refresh_token | TEXT      | NOT NULL                          | OAuth 2.0 refresh token              |
| token_expiry  | TIMESTAMP | NOT NULL                          | When access token expires            |
| last_sync_at  | TIMESTAMP | -                                 | Last email synchronization time      |
| is_active     | BOOLEAN   | DEFAULT 1                         | Whether connection is active          |
| created_at    | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP         | Connection creation timestamp         |

### processed_emails

| Column            | Type      | Constraints                        | Description                           |
|-------------------|-----------|-----------------------------------|---------------------------------------|
| id                | TEXT      | PRIMARY KEY, DEFAULT randomblob   | Unique email record identifier        |
| email             | TEXT      | NOT NULL                          | Gmail account that fetched this email |
| gmail_message_id  | TEXT      | UNIQUE NOT NULL                   | Gmail's unique message identifier     |
| subject           | TEXT      | -                                 | Email subject line                    |
| sender            | TEXT      | -                                 | Full sender info (name + email)      |
| sender_domain     | TEXT      | -                                 | Extracted domain from sender email   |
| received_at       | TIMESTAMP | -                                 | When email was originally received    |
| processed_at      | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP         | When record was created               |
| content           | TEXT      | -                                 | Full email body content (HTML/text)  |
| content_fetched   | BOOLEAN   | DEFAULT 0                         | Whether content has been fetched     |

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
| notes             | TEXT         | -                                 | Additional notes or information                 |
| created_by        | TEXT         | DEFAULT 'user'                    | Origin: user/gmail_import/llm                   |
| created_at        | TIMESTAMP    | DEFAULT CURRENT_TIMESTAMP         | When subscription was added                     |
| updated_at        | TIMESTAMP    | DEFAULT CURRENT_TIMESTAMP         | Last update timestamp                            |

### scratchpad

| Column          | Type      | Constraints                        | Description                              |
|-----------------|-----------|-----------------------------------|------------------------------------------|
| id              | TEXT      | PRIMARY KEY, DEFAULT randomblob   | Unique scratchpad item identifier        |
| item            | TEXT      | NOT NULL                          | User-entered subscription info           |
| processed       | BOOLEAN   | DEFAULT 0                         | Whether item has been processed         |
| created_at      | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP         | When item was added                      |

## Relationships

No formal foreign key relationships are implemented. Tables are independent but logically related:
- `processed_emails.email` indicates which Gmail account fetched the email
- `processed_emails.sender_domain` can be matched against `subscriptions.domains` (JSON array)
- Domain matching happens at query time rather than through database constraints

## Key Design Principles

1. **Subscriptions are standalone**: They don't require email/domain to exist
2. **Name is the primary identifier**: Users refer to subscriptions by name
3. **Domains are optional**: Stored as JSON array for flexibility
4. **Emails provide evidence**: They support and validate subscriptions but aren't required

## Constraints

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