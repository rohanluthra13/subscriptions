# Subscription Manager

A lightweight automated subscription tracking tool that monitors your Gmail inbox, identifies subscription-related emails, and extracts key information using LLM processing.

## Overview

This tool automatically:
- Monitors Gmail for subscription-related emails
- Uses LLM to classify and extract subscription data
- Tracks subscription details (vendor, amount, frequency, dates)
- Stores data locally for privacy
- Provides insights into your recurring expenses

## Features (Planned)

- Gmail integration for email ingestion
- LLM-powered email classification and data extraction
- Local storage for privacy-first approach
- Dashboard for subscription overview
- Alerts for upcoming renewals/expirations

## Tech Stack

### Core
- Node.js
- Next.js (Frontend & API)
- TypeScript
- Gmail API
- OpenAI API (GPT-4.1-nano)
- PostgreSQL (Database)

### MVP Dependencies
- Prisma (Database ORM)
- Tailwind CSS (Styling)
- Docker & Docker Compose (Self-hosting)

### Future Additions
- NextAuth.js (Multi-user auth)
- Zod (Response validation)
- node-cron (Scheduled email checks)
- React Query (Advanced data fetching)
- date-fns (Date utilities)

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

- **Self-hosted first**: Designed for Docker deployment with PostgreSQL
- **Privacy-focused**: All data stays on user's infrastructure
- **Reference**: Zero email app (`reference/zero-email/`) used for Gmail integration patterns

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