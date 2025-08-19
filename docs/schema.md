# Database Schema

SQLite database schema for the Subscription Manager application.

## Schema Diagram

```
┌─────────────────────┐    ┌─────────────────────────┐    ┌─────────────────────┐
│    connections      │    │   processed_emails      │    │   subscriptions     │
├─────────────────────┤    ├─────────────────────────┤    ├─────────────────────┤
│ id (TEXT)           │    │ id (TEXT)               │    │ id (TEXT)           │
│ email (TEXT) ◄──────┼────┤ email (TEXT)            │◄───┤ email (TEXT)        │
│ access_token (TEXT) │    │ gmail_message_id (TEXT) │    │ name (TEXT)         │
│ refresh_token (TEXT)│    │ subject (TEXT)          │    │ domain (TEXT) ◄─────┼─┐
│ token_expiry        │    │ sender (TEXT)           │    │ status (TEXT)       │ │
│ history_id (TEXT)   │    │ sender_domain (TEXT) ───┼────┤ renewing (BOOLEAN)  │ │
│ last_sync_at        │    │ received_at             │    │ cost (DECIMAL)      │ │
│ is_active (BOOLEAN) │    │ processed_at            │    │ billing_cycle (TEXT)│ │
│ created_at          │    │ is_subscription (BOOL)  │    │ next_date (DATE)    │ │
└─────────────────────┘    │ confidence_score (DEC)  │    │ created_at          │ │
                           │ vendor (TEXT)           │    │ updated_at          │ │
                           │ email_type (TEXT)       │    └─────────────────────┘ │
                           └─────────────────────────┘                            │
                                                                                  │
                           Domain matching: processed_emails.sender_domain ←──────┘
```

## Tables

### connections

| Column        | Type      | Constraints                        | Description                           |
|---------------|-----------|-----------------------------------|---------------------------------------|
| id            | TEXT      | PRIMARY KEY, DEFAULT randomblob   | Unique connection identifier          |
| email         | TEXT      | NOT NULL                          | Connected Gmail account email         |
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
| email               | TEXT        | NOT NULL                              | Gmail account that fetched this email   |
| gmail_message_id    | TEXT        | UNIQUE NOT NULL                       | Gmail's unique message identifier        |
| subject             | TEXT        | -                                     | Email subject line                      |
| sender              | TEXT        | -                                     | Full sender information                 |
| sender_domain       | TEXT        | -                                     | Extracted domain from sender email      |
| received_at         | TIMESTAMP   | -                                     | When email was originally received       |
| processed_at        | TIMESTAMP   | DEFAULT CURRENT_TIMESTAMP             | When record was created                  |
| is_subscription     | BOOLEAN     | DEFAULT 0                             | Whether email is subscription (deprecated) |
| confidence_score    | DECIMAL(3,2)| -                                     | LLM confidence score (0.00-1.00)        |
| vendor              | TEXT        | -                                     | Subscription service vendor name         |
| email_type          | TEXT        | -                                     | Type of subscription email               |

### subscriptions

| Column        | Type         | Constraints                        | Description                           |
|---------------|--------------|-----------------------------------|---------------------------------------|
| id            | TEXT         | PRIMARY KEY, DEFAULT randomblob   | Unique subscription identifier        |
| email         | TEXT         | NOT NULL                          | Gmail account this subscription belongs to |
| name          | TEXT         | NOT NULL                          | User-friendly name (e.g., "Netflix")  |
| domain        | TEXT         | NOT NULL                          | Primary domain (e.g., "netflix.com")  |
| status        | TEXT         | DEFAULT 'active'                  | active/cancelled/trial/paused         |
| renewing      | BOOLEAN      | DEFAULT 1                         | Whether subscription auto-renews      |
| cost          | DECIMAL(10,2)| -                                 | Cost per billing cycle                |
| billing_cycle | TEXT         | -                                 | monthly/yearly/quarterly              |
| next_date     | DATE         | -                                 | Next billing or expiry date          |
| created_at    | TIMESTAMP    | DEFAULT CURRENT_TIMESTAMP         | When subscription was added           |
| updated_at    | TIMESTAMP    | DEFAULT CURRENT_TIMESTAMP         | Last update timestamp                 |

## Relationships

```
connections.email ←── processed_emails.email
connections.email ←── subscriptions.email
processed_emails.sender_domain ←→ subscriptions.domain (for matching)
```

## Indexes

- UNIQUE(subscriptions.email, subscriptions.domain) - One subscription per domain per email account
- UNIQUE(processed_emails.gmail_message_id) - Prevent duplicate email processing

## Storage

Database file: `subscriptions.db` (SQLite file in application root directory)