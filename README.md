# mental_health_bot
MindCheck 🧠

AI-powered psychological self-monitoring bot for Telegram. Tracks mood, anxiety, energy and sleep — and helps make sense of the data through validated tests, personalized insights, and free-text AI chat.

Bot: @mindcheck_kz_bot

What It Does
🧪 Psychological tests — PHQ-9 (depression), GAD-7 (anxiety), Burnout (MBI), Self-esteem (Rosenberg), EQ. Each result comes with an AI explanation in plain language
✅ Daily check-ins — 5 questions: mood, anxiety, energy, sleep. Takes 1 minute
🔍 Personalized insights — delta-based analysis: reacts to actual changes between periods, not just averages. Recommends specific evidence-based practices with instructions
📈 Charts & history — dynamics of tests and check-ins over time
📅 Calendar view — 30-day mood overview at a glance
💬 Free-text AI chat — just type any question about your state or data. The bot answers using your actual check-in and test history. No buttons needed
🔔 Daily reminders — configurable check-in time
🌍 3 languages — Russian, Kazakh, English
Tech Stack
Layer	Technology
Framework	Python 3.13, aiogram 3
AI	Groq API (llama-3.3-70b-versatile)
Database	PostgreSQL + SQLAlchemy async
Hosting	Railway
Scheduler	APScheduler
Commands
Command	Description
/start	Start the bot
/help	Full feature list
/reminder	Change daily check-in reminder time
/language	Switch language (RU / KZ / EN)
Project Structure
bot/
├── main.py                   # Bot entry point, middleware, router registration
├── config.py                 # Environment variables
├── handlers/
│   ├── start.py              # /start, /help, /reminder
│   ├── tests.py              # Test flow (FSM)
│   ├── checkin.py            # Daily check-in (FSM)
│   ├── history.py            # Test history
│   ├── charts.py             # Dynamic charts
│   ├── insights.py           # Insights button handler
│   ├── calendar.py           # Calendar view
│   ├── feedback.py           # User feedback
│   ├── language.py           # Language selection
│   ├── admin.py              # Admin panel
│   └── chat.py               # Free-text AI chat handler
├── services/
│   ├── ai_explanation.py     # AI explanations for test results + weekly reflection
│   ├── insights.py           # Delta-based psychological insights
│   ├── scoring.py            # Test scoring logic
│   ├── reminders.py          # APScheduler daily reminders
│   ├── charts.py             # Chart generation
│   └── localization.py       # i18n loader
├── keyboards/
│   └── test_kb.py            # Reply keyboards
├── states/
│   └── test_states.py        # FSM states
└── locales/
    ├── ru.json               # Russian
    ├── kz.json               # Kazakh
    └── en.json               # English
database/
├── db.py                     # Async PostgreSQL connection
└── models.py                 # SQLAlchemy models: User, CheckIn, TestResult, UserStreak, Feedback
tests/
└── *.json                    # Test question banks (PHQ-9, GAD-7, Burnout, Self-esteem, EQ)
Environment Variables
env
BOT_TOKEN=          # Telegram bot token (BotFather)
GROQ_API_KEY=       # Groq API key (console.groq.com)
DATABASE_URL=       # PostgreSQL connection string (auto-set by Railway)
ADMIN_ID=           # Telegram user ID for admin panel
Key Design Decisions

Delta-based insights — instead of showing averages ("average anxiety: 6.2"), the bot compares current week vs previous week and reacts only to significant changes. This makes recommendations specific and actionable.

AI chat with user context — the free-text handler loads the user's last 30 check-ins and 10 test results, then passes them to the LLM. The bot can answer "compare my self-esteem results" or "what changed in my mood this month" with real data.

FSM-safe chat handler — the chat router is registered last, so it only catches messages not handled by test/check-in flows. Users in the middle of a test won't accidentally trigger the chat.

Principle-based AI prompts — system prompts define boundaries and style, not a fixed list of techniques. The LLM selects appropriate evidence-based practices (CBT, mindfulness, behavioural activation) based on the actual data.

Disclaimer

MindCheck is a self-monitoring tool, not a medical device. It does not provide diagnoses and does not replace a mental health professional. If test results concern you, please consult a specialist.

Author

Ratmir Mekenov — LinkedIn | GitHub
