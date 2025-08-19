# Database Schema

SQLite database schema for the Subscription Manager application.

## Schema Diagram

```
┌─────────────────────┐    ┌─────────────────────────┐
│    connections      │    │   processed_emails      │
├─────────────────────┤    ├─────────────────────────┤
│ id (TEXT)           │◄───┤ connection_id (TEXT)    │
│ email (TEXT)        │    │ id (TEXT)               │
│ access_token (TEXT) │    │ gmail_message_id (TEXT) │
│ refresh_token (TEXT)│    │ subject (TEXT)          │
│ token_expiry        │    │ sender (TEXT)           │
│ history_id (TEXT)   │    │ sender_domain (TEXT)    │
│ last_sync_at        │    │ subscription_status     │
│ is_active (BOOLEAN) │    │ user_selected (BOOLEAN) │
│ created_at          │    │ received_at             │
└─────────────────────┘    │ processed_at            │
                           │ is_subscription (BOOL)  │
                           │ confidence_score (DEC)  │
                           │ vendor (TEXT)           │
                           │ email_type (TEXT)       │
                           └─────────────────────────┘
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
| connection_id       | TEXT        | NOT NULL, FK(connections)             | Reference to connections table           |
| gmail_message_id    | TEXT        | UNIQUE NOT NULL                       | Gmail's unique message identifier        |
| subject             | TEXT        | -                                     | Email subject line                      |
| sender              | TEXT        | -                                     | Full sender information                 |
| sender_domain       | TEXT        | -                                     | Extracted domain from sender email      |
| subscription_status | TEXT        | DEFAULT NULL                          | Classification: active/inactive/trial/not_subscription |
| user_selected       | BOOLEAN     | DEFAULT 0                             | Whether classification was user-selected |
| received_at         | TIMESTAMP   | -                                     | When email was originally received       |
| processed_at        | TIMESTAMP   | DEFAULT CURRENT_TIMESTAMP             | When record was created                  |
| is_subscription     | BOOLEAN     | DEFAULT 0                             | Whether email is subscription            |
| confidence_score    | DECIMAL(3,2)| -                                     | LLM confidence score (0.00-1.00)        |
| vendor              | TEXT        | -                                     | Subscription service vendor name         |
| email_type          | TEXT        | -                                     | Type of subscription email               |

## Relationships

```
connections (1) ──────────── (many) processed_emails
```

## Storage

Database file: `subscriptions.db` (SQLite file in application root directory)