# InstaManager

Multi-account Instagram operations console with an AI copilot. Manage dozens of accounts from a single dashboard — login, post, engage, monitor, and automate through a clean web interface or natural-language commands.

## Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.12, FastAPI, instagrapi, LangGraph |
| Frontend | React 19, TypeScript, Vite 8, Tailwind CSS 4 |
| AI | LangGraph workflows, multi-provider LLM (OpenAI, Gemini, DeepSeek, Claude) |
| Persistence | In-memory (dev), SQLite, PostgreSQL |

## Quick Start

```bash
# 1. Clone and set up backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # edit with your API keys

# 2. Set up frontend
cd ../frontend
npm install

# 3. Run both (from project root)
./scripts/start.sh
```

Frontend runs on `http://localhost:5173`, backend on `http://localhost:8000`.

## Features

### Account Management
- Multi-account login with 2FA/TOTP support
- Session import/export and credential batch import
- Proxy assignment per account
- Bulk operations (relogin, logout, proxy set)
- Session health tracking and auto-recovery

### Content & Publishing
- Post scheduling with multi-account targeting
- Photo, video, reels, album, and IGTV support
- Caption templates with tag management
- Story publishing and highlight management

### Relationships
- Follow/unfollow with batch operations (SSE streaming)
- Cross-follow detection and execution
- Follower/following search (server-side)
- Remove follower, close friends management

### Discovery & Analytics
- Hashtag and location-based discovery
- Media insights and engagement stats
- Collection browsing
- Direct message management

### AI Copilot
- **Operator Copilot** — 9-node LangGraph workflow that translates natural-language commands into Instagram operations with human-in-the-loop approval for write actions
- **Smart Engagement** — 11-node automated engagement workflow with candidate discovery, risk scoring, and circuit breakers
- Tool policy enforcement (read-only / write-sensitive / blocked)
- Cross-thread memory for engagement outcomes and interaction history

### Security
- Optional dashboard login page gated on `ENABLE_DASHBOARD_AUTH` — stateless JWT auth, 24-hour tokens
- Optional backend API key (`API_KEY` env var) enforced via `X-API-Key` header on every request
- API key configurable from the Settings page without a code deploy

### Infrastructure
- Proxy pool management with health checking
- Rate limiting and circuit breakers
- Encrypted credential storage (Fernet)
- Catalog-based error translation
- Non-blocking login — Instagram network I/O outside DB transactions, profile hydration via background tasks
- SSE endpoint (`GET /api/accounts/events`) pushes real-time account updates (followers/following) to the frontend after background hydration completes

## Architecture

```
backend/
  app/
    adapters/         # HTTP routers, Instagram SDK, persistence, AI providers
    application/      # Use cases, ports (Protocol), DTOs
    bootstrap/        # Dependency injection container
  ai_copilot/
    application/      # LangGraph graphs, nodes, state, policy
    adapters/         # Memory, circuit breaker, executors

frontend/src/
  pages/              # Thin page shells
  features/           # Feature-colocated modules (components, hooks, types)
  components/ui/      # Shared design system
  store/              # Zustand state management
  api/                # Axios API client
```

Dependencies point inward: `adapters -> application -> ports <- adapters`. The application layer never imports vendor SDKs.

## Environment

Minimum for dev: `PERSISTENCE_BACKEND=memory` + one AI provider key in `backend/.env`.

See `backend/.env.example` for the full configuration reference.

## Tests

```bash
# Root-level tests
pytest tests/ -v

# Backend-internal tests
cd backend && pytest tests/ -v

# Smart engagement + LangGraph tests
PYTHONPATH=tests/_stubs:backend pytest tests/test_smart_engagement_*.py -v
```

## License

Private repository. All rights reserved.
