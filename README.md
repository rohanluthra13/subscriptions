# Subscription Manager

A simplified, AI-agent-friendly subscription tracking application that automatically identifies and manages subscriptions from your Gmail inbox using LLM processing.

## 🎯 What It Does

- **Connects to Gmail** via OAuth to access your emails
- **Processes emails** using OpenAI to identify subscription-related content  
- **Extracts subscription data** like vendor, amount, billing cycle
- **Provides a web dashboard** to view and manage your subscriptions
- **Works locally** with SQLite database - no cloud dependencies

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Gmail account
- OpenAI API key
- Google Cloud Console project (for Gmail OAuth)

### Installation & Setup

1. **Clone and enter directory**
   ```bash
   git clone <repository-url>
   cd subscriptions
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Mac/Linux
   # or
   venv\Scripts\activate     # On Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   - Copy `.env.example` to `.env` (if exists) or create `.env`:
   ```bash
   # Google OAuth (get from Google Cloud Console)
   GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-client-secret
   
   # OpenAI API
   OPENAI_API_KEY=sk-your-openai-api-key
   OPENAI_MODEL=gpt-4o-mini
   
   # App settings
   LLM_CONFIDENCE_THRESHOLD=0.7
   API_KEY=your-secure-api-key
   ```

5. **Configure Google OAuth**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Enable Gmail API
   - Create OAuth 2.0 credentials
   - Add redirect URI: `http://localhost:8000/auth/callback`

6. **Run the application**
   ```bash
   python main.py
   ```

7. **Open your browser**
   - Go to `http://localhost:8000`
   - Connect your Gmail account
   - Start syncing emails!

## 📱 Usage

### Dashboard Features

**Three Main Tabs:**
- **All Emails** - View all processed emails
- **Classified** - View emails identified as subscriptions
- **Subscriptions** - Summary of detected subscriptions

### Email Sync Options

**Batch Sizes:** 5, 30, 100, or 500 emails per sync

**Sync Directions:**
- **Recent emails** - Process most recent emails
- **Older emails** - Process older emails from your last sync point

### Managing Data

**Reset Database:**
- Via web: Visit `http://localhost:8000/reset`
- Via command line: `rm subscriptions.db`

## 🏗️ Architecture

### Design Philosophy
This application is built with **AI agent maintainability** in mind:
- Single file architecture (`main.py`)
- Direct SQL (no ORM abstractions)
- Minimal dependencies
- Local-first design
- No build processes or complex tooling

### Technology Stack
- **Python 3.9+** with built-in HTTP server
- **SQLite** for local data storage
- **Gmail API** for email access
- **OpenAI API** for intelligent email classification
- **HTML/CSS/JavaScript** for web interface (no frameworks)

### File Structure
```
/
├── main.py              # Complete application (~500 lines)
├── requirements.txt     # Just 2 dependencies!
├── subscriptions.db     # SQLite database (auto-created)
├── .env                # Your configuration
├── venv/               # Python virtual environment
└── reference-typescript/   # Legacy complex version
```

## 🖥️ Desktop Distribution

This application is designed for easy desktop distribution:

### Creating Standalone App
```bash
# Install PyInstaller
pip install pyinstaller

# Create standalone executable
pyinstaller --onefile --name "Subscription Manager" main.py

# Distributable app will be in dist/ folder
```

### Distribution Benefits
- **Single executable** - no installation required
- **Local database** - works offline except for API calls
- **Cross-platform** - Windows, Mac, Linux
- **No dependencies** - users just download and run

## 🔧 Development

### Making Changes
1. Edit `main.py` directly
2. Restart: `python main.py`
3. Test at `http://localhost:8000`

### Database Management
- Schema is defined in the `init_database()` function
- To reset: delete `subscriptions.db` and restart
- All data is stored locally in SQLite

### Adding Features
- Add functions directly to `main.py`
- Extend database schema as needed
- Add new HTTP routes in the `do_GET()` method
- Update HTML templates inline

## 🆚 Comparison with Complex Architecture

The `reference-typescript/` folder contains the previous implementation:

| Aspect | Python Version | TypeScript Version |
|--------|---------------|-------------------|
| **Files** | 1 file | 78+ files |
| **Lines of Code** | ~500 lines | 7,440+ lines |
| **Dependencies** | 2 packages | 100+ packages |
| **Database** | SQLite file | PostgreSQL server |
| **Deployment** | Single executable | Docker containers |
| **Setup Time** | 2 minutes | 15+ minutes |

**Same functionality, 95% less complexity.**

## 🤝 Contributing

This codebase prioritizes:
1. **Simplicity** over complexity
2. **Direct implementation** over abstraction layers  
3. **AI agent maintainability** over human developer convenience
4. **Local-first** over cloud-dependent

When contributing:
- Keep everything in `main.py` unless absolutely necessary
- Use direct SQL instead of ORMs
- Avoid adding dependencies unless essential
- Test the complete flow end-to-end

## 📄 License

[Add your license here]

## 🆘 Support

Having issues? Check:
1. All environment variables are set correctly
2. Google OAuth redirect URI is configured
3. OpenAI API key has sufficient credits
4. Gmail API is enabled in Google Cloud Console

## 🔮 Future Enhancements

Planned features:
- [ ] Export subscriptions to CSV
- [ ] Subscription cancellation tracking
- [ ] Cost analysis and budgeting
- [ ] Mobile-responsive design improvements
- [ ] Bulk subscription management

---

**Built for the AI agent era** - Simple, direct, and maintainable. 🤖