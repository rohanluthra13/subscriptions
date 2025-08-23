# CLAUDE.md

This file provides guidance to Claude Code when working with this subscription management project.

## Project Overview

**Subscription Manager** - An AI-assisted subscription tracking tool that analyzes Gmail to identify and manage subscriptions. Originally a standalone Python app, now evolving toward MCP (Model Context Protocol) integration for seamless AI agent interaction.

**Philosophy**: Local-first, non-subscription tool that leverages existing AI services rather than adding another subscription.

## Quick Start

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run current standalone version
python main.py
# Access at: http://localhost:8000

# Reset database if needed
rm subscriptions.db
```

## Current Architecture

**Single-file Python app** (`main.py` - ~1100 lines)
- SQLite database for local storage
- Gmail API integration with OAuth
- Multi-threaded HTTP server with background jobs
- Simple web UI for viewing results
- MCP server integration for AI agent interaction
- Domain-based subscription detection

**MCP Integration** (active - see `mcp_server.py`)
- Expose subscription data via MCP protocol  
- AI agents can query and manage subscriptions
- Background job system for long-running operations
- Local storage with AI interaction capability

## File Structure

```
/
├── main.py              # Complete application (~1000 lines)
├── requirements.txt     # Python dependencies  
├── subscriptions.db     # SQLite database (auto-created)
├── .env                # Environment variables
├── docs/               # MCP migration planning
│   ├── manifesto.md    # Project philosophy
│   ├── product.md      # MCP product specs
│   └── technical.md    # Technical approach
└── reference-typescript/   # Original complex implementation
```

## Environment Setup

Required `.env` variables:
```bash
# Google OAuth (from Google Cloud Console)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret

# OpenAI API (for subscription classification)
OPENAI_API_KEY=sk-your-api-key
OPENAI_MODEL=gpt-4o-mini
```

## How It Works

1. **Gmail Connection**: OAuth flow to access email metadata
2. **Domain Clustering**: Groups emails by sender domain 
3. **Manual Classification**: User marks domains as subscriptions/not subscriptions
4. **Subscription Detection**: Identifies subscription patterns and costs
5. **Local Storage**: All data stays in local SQLite database

## Development Notes

- Single-file architecture - everything in `main.py` 
- Direct SQL queries - no ORM complexity
- Multi-threaded HTTP server with background job management
- Local-first - works offline except for API calls
- MCP server enables AI agent integration

## Key Database Tables

- `connections` - Gmail OAuth tokens
- `processed_emails` - Email metadata and sender domains
- `subscriptions` - Detected subscription details
- `scratchpad` - Manual subscription entry items

## MCP Migration (Future)

See `docs/` folder for planning:
- `manifesto.md` - Project philosophy and goals
- `product.md` - MCP integration specs
- `technical.md` - Implementation approach

Goal: Transform from standalone app to MCP server that AI agents can query for subscription management.

Practices
- when you update the database always update the docs/schema.md file as well to ensure they are both aligned