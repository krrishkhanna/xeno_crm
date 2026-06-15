# Xeno CRM

An AI-native mini CRM for shopper marketing. The product is designed around a natural-language agent that plans campaigns, creates segments, drafts copy, and dispatches communications through a stubbed channel service.

Live frontend: `https://krrishkhanna.github.io/xeno_crm/` after GitHub Pages is enabled on the repository.

## Architecture

- `CRM backend`: FastAPI app on port `8000`
- `Channel service`: FastAPI simulator on port `8001`
- `Database`: Supabase/Postgres
- `AI`: OpenAI-backed planner with a local fallback if the key is unavailable
- `Frontend`: static GitHub Pages UI in `frontend/`

## Agent Workflow

1. A marketer sends a plain-language prompt.
2. The agent turns the prompt into an objective and segment definition.
3. The CRM queries matching customers and drafts campaign copy.
4. The campaign is created, queued, and sent to the channel service.
5. The channel service simulates delivery and calls back into the CRM.
6. The CRM updates communication state and campaign analytics.

## Data Model

- `customers`: shopper profile, city, tags, order count, last order date
- `orders`: customer purchase history
- `campaigns`: campaign name, message, segment definition, status
- `communications`: per-recipient lifecycle, provider metadata, failure reason

## API Surface

CRM backend:

- `GET /health`
- `POST /api/v1/agent/chat`
- `POST /api/v1/agent/chat/stream`
- `GET /api/v1/campaigns`
- `POST /api/v1/campaigns`
- `POST /campaigns/send`
- `GET /api/v1/campaigns/{campaign_id}/analytics`
- `GET /api/v1/communications`
- `POST /api/v1/communications/callbacks/channel-service`

Channel service:

- `GET /health`
- `POST /send`

## Production Setup

### 0. GitHub Pages frontend

The frontend is a static app served from `frontend/` and deployed by GitHub Actions to GitHub Pages.

- Repository source: `main` branch
- Publish source: GitHub Actions
- Public URL: `https://krrishkhanna.github.io/xeno_crm/`

### 1. Render deployment

This repo includes `render.yaml`, plus Dockerfiles for both services.

Deploy the repo to Render as two web services:

- `xeno-crm-backend`
- `xeno-channel-service`

Render will assign each service a public URL automatically.

### 2. Environment variables

CRM backend:

```env
DATABASE_URL=postgresql+asyncpg://...
CHANNEL_SERVICE_URL=https://<your-channel-service-url>
CRM_PUBLIC_URL=https://<your-crm-url>
CRM_CALLBACK_URL=https://<your-crm-url>/api/v1/communications/callbacks/channel-service
MARKETING_AGENT_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
```

Channel service:

```env
CALLBACK_TIMEOUT_SECONDS=10
PROVIDER_MIN_DELAY_SECONDS=1
PROVIDER_MAX_DELAY_SECONDS=5
CALLBACK_USER_AGENT=channel-service/1.0
```

### 3. Supabase

- Create a Supabase project.
- Copy the Postgres connection string into `DATABASE_URL`.
- Let the CRM boot once so it creates the tables, or apply your own migrations if you prefer.

## Local Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

```bash
cd channel-service
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

## Demo Steps

1. Seed customers and orders.
2. Start both services.
3. Send these prompts to `POST /api/v1/agent/chat` with `provider: "local"` if you want the fallback planner:
   - “Send a win-back campaign to dormant customers”
   - “Create a loyalty campaign for high-value customers”
   - “Send a welcome campaign to new customers”
4. Check `GET /api/v1/campaigns/{campaign_id}/analytics`.
5. Check `GET /api/v1/communications` to watch delivery statuses move through the lifecycle.
6. Open the GitHub Pages frontend and use the in-page buttons to run the same flows.

## Verification

```bash
python3 -m compileall app channel-service/app
```

Then run the three assignment scenarios end to end and confirm callbacks update the communication records.
