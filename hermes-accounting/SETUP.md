# Hermes Accounting — Setup Guide

## Prerequisites
- Python 3.11+
- Node.js 20+
- Hermes Agent installed (curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash)

## Quick Start

### 1. Backend
```bash
cd backend
pip install -r requirements.txt

# Run accounting API
uvicorn main:app --port 8000 --reload

# Run MCP server (separate terminal)
python mcp_serve.py --port 8001
```

### 2. Frontend
```bash
cd frontend
npm install
npm run dev
# Runs on http://localhost:5173
```

### 3. Hermes Agent
```bash
# Copy hermes config
cp -r hermes ~/.hermes-accounting

# Configure Hermes to use this project's skills and MCP server
hermes config set mcp.servers.hermes-accounting http://localhost:8001/mcp
hermes config set skills.external_dirs "[\"$(pwd)/hermes/skills\"]"

# Set your model (get key from openrouter.ai)
hermes model  # interactive model selector

# Start the gateway (for WhatsApp/Telegram)
hermes gateway setup
hermes gateway start

# Register nightly cron
hermes cron add "0 23 * * *" /nightly-accounting-review

# Start chatting
hermes
```

### 4. Docker (all-in-one)
```bash
cp .env.example .env
# Edit .env with your API keys
docker compose up
```

## Environment Variables
```
# Backend
DATABASE_URL=sqlite:///./hermes_accounting.db
HERMES_GATEWAY_URL=http://localhost:5000/api/chat
HERMES_MCP_URL=http://localhost:8001/mcp
HERMES_API_KEY=

# Frontend
VITE_API_URL=http://localhost:8000

# Hermes (in ~/.hermes/.env)
OPENROUTER_API_KEY=sk-or-...
WHATSAPP_TOKEN=
TELEGRAM_BOT_TOKEN=
```

## How Hermes Integration Works

### Level 1 — Chat bar (frontend)
User types in the chat bar → POST /api/hermes/query →
backend injects full ledger context → calls Hermes gateway →
streams response back to frontend.

### Level 2 — MCP tools (autonomous actions)
Hermes can call record_entry, query_ledger, get_creditor_balance,
get_month_end_summary, set_period_lock via the MCP server at port 8001.
Triggered by: WhatsApp receipt photos, voice commands, or the chat bar.

### Level 3 — Cron (nightly review)
Hermes runs at 23:00 daily, calls the accounting API,
composes a summary, and delivers via WhatsApp.

## Conversation Starters for Hermes
- "Which entries are missing supporting documents?"
- "What is Asia Trade Centre's outstanding balance?"
- "Summarise this month's purchases"
- "Flag any invoices that look anomalous"
- "Is May 2026 ready to lock?"
- "Process this receipt [attach photo]"

## Adding Malaysian Tax Knowledge
Skills live in hermes/skills/. Add new SKILL.md files for:
- SST treatment rules (hermes/skills/sst-treatment/SKILL.md)
- LHDN e-invoicing (hermes/skills/lhdn-einvoicing/SKILL.md)
- MPERS standards (hermes/skills/mpers-standards/SKILL.md)
- CP204 estimation (hermes/skills/cp204/SKILL.md)

Hermes loads them on demand — they only consume tokens when relevant.
