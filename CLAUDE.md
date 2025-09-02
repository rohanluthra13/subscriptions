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

**Single-file Python app** (`main.py` - ~1900 lines)
- SQLite database for local storage
- Gmail API integration with OAuth
- Multi-threaded HTTP server with background jobs
- Modern SPA-style web UI with smooth navigation
- MCP server integration for AI agent interaction
- Domain-based subscription detection

**Architecture Philosophy: "HTML Over The Wire" + Agent-First**
- **Server-side rendering**: Python builds complete HTML using templates
- **Minimal JavaScript**: Just enough for smooth SPA-like navigation (~500-800 lines)
- **Template-based presentation**: Clean separation of data preparation and UI rendering
- **Progressive enhancement**: Works without JavaScript, enhanced with it
- **Single-file simplicity**: Everything in `main.py` for complete AI agent context
- **No complex frameworks**: Avoids React/Angular complexity while achieving modern UX

**Architectural Alignment**: Similar to Basecamp's Turbo approach - server handles business logic and HTML generation, minimal client-side JavaScript manages navigation and interactions.

**MCP Integration** (active - see `mcp_server.py`)
- Expose subscription data via MCP protocol  
- AI agents can query and manage subscriptions
- Background job system for long-running operations
- Local storage with AI interaction capability

## File Structure

```
/
├── main.py              # Complete application (~1900 lines)
├── requirements.txt     # Python dependencies  
├── subscriptions.db     # SQLite database (auto-created)
├── .env                # Environment variables
├── templates/          # HTML Over The Wire templates
│   ├── base.html       # SPA shell with navigation and core JS
│   └── views/          # View fragments loaded via AJAX
│       ├── home.html   # Summary dashboard
│       ├── manage.html # Subscription management
│       ├── emails.html # Gmail integration
│       ├── review.html # LLM findings review
│       └── notepad.html# User notes
├── docs/               # Architecture documentation
│   ├── #LLMbriefs/     # Agent review documents
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
3. **LLM Analysis**: AI analyzes patterns and writes findings to `resources/llm_notes.md`
4. **User Review**: Interactive UI at `/?view=review` for confirming/rejecting findings
5. **Subscription Management**: Full CRUD operations with inline editing at `/?view=manage`
6. **Local Storage**: All data stays in local SQLite database

## Development Notes

**Architecture Principles:**
- **"HTML Over The Wire"**: Server renders HTML, minimal JS handles navigation
- **Single-file main logic**: Core business logic in `main.py` for AI agent comprehension
- **Template-driven UI**: Clean separation between data preparation and presentation
- **Progressive enhancement**: Functional without JS, smooth with JS enabled
- **Direct SQL**: No ORM complexity, explicit database operations
- **Multi-threaded server**: Background job management for long-running operations
- **Local-first**: Works offline except for Gmail/OpenAI API calls

**Maintenance Philosophy:**
- Keep server-side logic simple and traceable
- Avoid complex client-side state management
- Use JavaScript for navigation/UX, not business logic
- Maintain agent-friendly single-file approach while using templates for presentation

## Key Database Tables

- `connections` - Gmail OAuth tokens
- `processed_emails` - Email metadata and sender domains
- `subscriptions` - Detected subscription details

## Review Workflow

- LLM findings stored in `resources/llm_notes.md`
- Review UI at `/?view=review` for user confirmation
- Markdown format with User Check (Yes/No) and User Notes fields

## MCP Migration (Future)

See `docs/` folder for planning:
- `manifesto.md` - Project philosophy and goals
- `product.md` - MCP integration specs
- `technical.md` - Implementation approach

Goal: Transform from standalone app to MCP server that AI agents can query for subscription management.

Practices
- when you update the database always update the docs/schema.md file as well to ensure they are both aligned
- you should run this in a venv using python main.py