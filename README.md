# Subscription Manager

A lightweight automated subscription tracking tool that processes your Gmail inbox daily, identifies subscription-related emails, and extracts key information using LLM processing.

## Overview

This tool automatically:
- Processes Gmail inbox daily for subscription-related emails
- Uses LLM to detect and extract subscription data
- Tracks subscription details (vendor, amount, frequency, dates)
- Stores only subscription metadata locally for privacy (no email content)
- Provides insights into your recurring expenses via web dashboard

## MVP Features

- Gmail OAuth integration for secure email access
- Daily batch processing with manual refresh capability
- LLM-powered subscription detection and data extraction
- On-demand email fetching (no email content storage)
- Web dashboard for subscription management
- Search, filter, and sort subscriptions
- CSV export functionality
- Edit and delete subscription entries

## Tech Stack

### Core Stack
- **Runtime**: Node.js 20+ with TypeScript
- **Framework**: Next.js 14 (App Router)
- **Database**: PostgreSQL 17 with Prisma ORM
- **Styling**: Tailwind CSS
- **Deployment**: Docker Compose

### External Services
- **Email**: Gmail API v1
- **LLM**: OpenAI API (model TBD)
- **Auth**: Google OAuth 2.0

### MVP Dependencies
- Prisma (Database ORM)
- Tailwind CSS (Styling)
- Docker & Docker Compose (Self-hosting)
- node-cron (Daily batch processing)

### Future Additions
- NextAuth.js (Multi-user auth)
- Zod (Response validation)
- React Query (Advanced data fetching)
- date-fns (Date utilities)
- Email notifications (renewal reminders)

## Documentation

- **Planning**: [`docs/planning/`](docs/planning/)
  - [PRD.md](docs/planning/PRD.md) - Product requirements
  - [PLAN.md](docs/planning/PLAN.md) - Development plan
- **Architecture**: [`docs/architecture/`](docs/architecture/)
  - [DESIGN.md](docs/architecture/DESIGN.md) - Technical design
  - [zero_analysis.md](docs/architecture/zero_analysis.md) - Zero email analysis
- **Decisions**: [`docs/decisions/`](docs/decisions/)
  - [DECISIONS.md](docs/decisions/DECISIONS.md) - Architectural decisions log

## Architecture

- **Daily Batch Processing**: Processes emails every 24 hours with manual refresh capability
- **On-Demand Email Fetching**: No email content stored - fetches from Gmail API when needed
- **Single-User MVP**: Hardcoded user_id='1' with multi-user database schema foundation
- **Self-hosted first**: Designed for Docker Compose deployment with PostgreSQL
- **Privacy-focused**: Only subscription metadata stored, all data stays on user's infrastructure

## Development

```bash
# Install dependencies
npm install

# Set up environment variables
cp .env.example .env

# Run development server
npm run dev
```

## Status

🚧 **In Development** - Currently in planning phase

## License

TBD