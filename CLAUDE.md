# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this Python-based subscription manager.

## Project Overview

**Subscription Manager** - A simplified, AI-agent-friendly subscription tracking tool that processes Gmail inbox, identifies subscription emails using LLM processing, and extracts subscription data. Built as a single-file Python application with SQLite for easy deployment and maintenance.

**Architecture Philosophy**: Optimized for AI agent development - minimal abstractions, direct implementations, single-file simplicity over human developer convenience layers.

## Development Commands

### Running the Application
```bash
# Setup (first time)
python -m venv venv
source venv/bin/activate  # On Mac/Linux
pip install -r requirements.txt

# Run application
python main.py

# Access at: http://localhost:8000
```

### Database Management
```bash
# Reset database (clear all data)
rm subscriptions.db

# Or via web interface
# Visit: http://localhost:8000/reset
```

### Desktop App Packaging (Future)
```bash
# Install PyInstaller
pip install pyinstaller

# Create desktop app
pyinstaller --onefile --name "Subscription Manager" main.py

# Distributable app will be in dist/ folder
```

## Architecture

### Core Design Principles
- **Single file architecture** - All logic in `main.py`
- **Direct SQL** - No ORM abstractions
- **Embedded SQLite** - No external database server
- **Minimal dependencies** - Only essential packages
- **Local-first** - Works offline except for API calls

### Technology Stack
- **Python 3.9+** - Core runtime
- **SQLite** - Local database (file-based)
- **HTML/CSS/JS** - Direct templates (no frameworks)
- **Gmail API** - Email access via OAuth 2.0  
- **OpenAI API** - LLM-powered email classification

### Application Flow
1. **Gmail OAuth** - One-time user authorization
2. **Email Fetching** - Direct Gmail API calls
3. **LLM Processing** - OpenAI classification
4. **SQLite Storage** - Local database persistence
5. **Web Interface** - Built-in HTTP server with HTML templates

## File Structure

```
/
├── main.py              # Complete application (400+ lines)
├── requirements.txt     # Python dependencies
├── subscriptions.db     # SQLite database (auto-created)
├── .env                # Environment variables
├── venv/               # Python virtual environment
└── reference-typescript/   # Legacy TypeScript implementation
```

## Database Schema

SQLite tables (defined in `main.py`):
- **users** - User accounts (hardcoded single user for MVP)
- **connections** - Gmail OAuth tokens and connection state
- **subscriptions** - Detected subscription metadata
- **processed_emails** - Email processing log (prevents duplicates)

## Environment Setup

Required `.env` variables:
```bash
# Google OAuth (Google Cloud Console)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret

# OpenAI API
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_MODEL=gpt-4o-mini  # or gpt-5-nano

# Application Settings
LLM_CONFIDENCE_THRESHOLD=0.7
API_KEY=your-secure-api-key
```

## Key Implementation Details

### Single-File Architecture
- All functionality contained in `main.py`
- No separate modules unless complexity truly demands it
- Direct function calls instead of class hierarchies
- Embedded HTML templates as Python strings

### Direct Database Access
```python
# Direct SQL - no ORM translation layer
conn = sqlite3.connect("subscriptions.db")
cursor = conn.cursor()
cursor.execute("SELECT * FROM subscriptions WHERE user_id = ?", (user_id,))
results = cursor.fetchall()
```

### Embedded Web Server
```python
# Built-in HTTP server - no framework overhead  
from http.server import HTTPServer, BaseHTTPRequestHandler
# Custom request handler with inline HTML templates
```

### API Integration
```python
# Direct API calls - no SDK abstraction layers
response = requests.post('https://api.openai.com/v1/chat/completions', 
                        headers=headers, json=data)
```

## Development Workflow

### Making Changes
1. Edit `main.py` directly
2. Restart: `python main.py`
3. Test at `http://localhost:8000`

### Adding Features
- Add functions directly to `main.py`
- Extend SQLite schema in `init_database()`
- Add new HTTP routes in `do_GET()`
- Update HTML templates inline

### Database Changes
1. Modify table creation in `init_database()`
2. Delete `subscriptions.db` to recreate with new schema
3. Or add migration logic if preserving data

## Web Interface

### Three-Tab Dashboard
- **All Emails** - Shows all processed emails
- **Classified** - Shows emails identified as subscriptions
- **Subscriptions** - Shows final subscription summaries

### Sync Controls
- Email count: 5, 30, 100, 500
- Direction: Recent emails or older emails
- Real-time processing feedback

### API Endpoints
- `/` - Main dashboard
- `/auth/gmail` - Gmail OAuth flow
- `/sync` - Email sync with parameters
- `/api/emails` - Email data for tabs
- `/reset` - Clear all data

## Testing & Debugging

### Manual Testing
1. Start app: `python main.py`
2. Connect Gmail account
3. Sync emails with different settings
4. Verify data in all tabs
5. Test reset functionality

### Debug Information
- OpenAI API responses logged to terminal
- Email processing progress shown
- SQL errors displayed clearly

## Desktop Distribution

### Packaging for Users
1. Use PyInstaller to create standalone executable
2. SQLite database created in user's local folder
3. No installation required - just download and run
4. Cross-platform compatibility (Mac, Windows, Linux)

### Distribution Benefits
- Single file download
- No Docker, PostgreSQL, or Node.js dependencies
- Works offline except for API calls
- Automatic local database creation

## Migration from TypeScript Version

The TypeScript implementation (in `reference-typescript/`) demonstrates the complexity difference:
- **78 files vs 1 file**
- **7,440 lines vs 400 lines**
- **100+ dependencies vs 2 dependencies**
- **Multi-container deployment vs single executable**

This Python version delivers identical functionality with 95% less complexity, optimized for AI agent development and easy user distribution.

## Common Patterns

### Database Operations
```python
def get_subscriptions():
    conn = sqlite3.connect("subscriptions.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM subscriptions ORDER BY created_at DESC")
    return cursor.fetchall()
```

### API Calls
```python
def call_openai_api(prompt):
    headers = {'Authorization': f'Bearer {openai_api_key}'}
    response = requests.post(url, headers=headers, json=data)
    return response.json()
```

### HTML Generation
```python
def render_dashboard():
    return f"""
    <html>
        <body>
            <h1>Dashboard</h1>
            {render_subscriptions_table()}
        </body>
    </html>
    """
```

## Development Philosophy

This codebase prioritizes:
1. **AI agent maintainability** over human developer convenience
2. **Direct implementation** over abstraction layers
3. **Single-file simplicity** over modular complexity
4. **Immediate deployment** over build processes
5. **Local-first operation** over cloud dependencies

The result is a subscription manager that's easier to understand, modify, and distribute than traditional web application architectures.