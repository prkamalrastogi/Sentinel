# Sentinel - GCC Energy Escalation Simulator

Secure web-based decision-support prototype that translates escalation conditions into structured operational and financial exposure for GCC energy companies.

## Core principle

Sentinel **does not predict conflict outcomes**.
It translates escalation conditions into structured exposure bands for planning and stress-testing.

## Scope implemented

- Geographic focus:
  - GCC states
  - Strait of Hormuz
- Escalation Tier Engine:
  - Tier 0 - Normal stability
  - Tier 1 - Limited strike exchange
  - Tier 2 - Sustained cross-border attacks
  - Tier 3 - Regional proxy spillover
  - Tier 4 - Hormuz disruption
- Oil Regime Simulator (range-based) for 7/30/90 days
- Export Disruption Model:
  - throughput reduction %
  - shipping insurance premium increase %
  - LNG delay probability %
  - refinery margin stress indicator
- Company Exposure Dashboard (ENOC proxy profile, editable):
  - revenue impact band
  - liquidity stress indicator
  - export disruption severity
  - risk heat map
- Trigger-based auto-upgrade logic:
  - missile strike on export terminal
  - naval blockade alert
  - insurance market withdrawal
- Live internet intelligence module:
  - pulls public live news threads from multiple feeds (Google News RSS, Reuters, AP, BBC, CNN, Al Jazeera, Reddit RSS)
  - integrates optional leading news APIs in parallel (NewsAPI, GNews, Guardian Open Platform, New York Times, Mediastack)
  - classifies headline signals (`critical`, `elevated`, `watch`) with transparent keyword rules
  - creates alert-level advisory and recommended operational/financial steps
- Sentinel advisor chatbot:
  - asks plain-language questions against the active scenario context
  - returns direct "what to do next" actions with supporting live-signal links
  - supports optional LLM mode when `SENTINEL_OPENAI_API_KEY` is configured
- External Intel Grid:
  - embeds World Monitor URL, YouTube live sources, and live cam URLs as plugin panels
- Learning Lab:
  - stores operator post-incident outcomes and lessons
  - reuses relevant lessons during advisor responses
- World Monitor connector layer:
  - normalizes live headlines into structured global events (event type, severity, region, confidence, assets)
  - provides region/type/severity heatmaps before Sentinel consequence translation

## Security controls

- Optional API key authentication (`X-API-Key`) via `SENTINEL_API_KEYS`
- CORS restricted by `SENTINEL_ALLOWED_ORIGINS`
- Request rate limiting (in-memory) via `SENTINEL_RATE_LIMIT_PER_MINUTE`
- Request size guard via `SENTINEL_MAX_BODY_BYTES`
- Security response headers (frame/content/referrer/cache hardening)
- Strict request schema validation (`extra="forbid"`)

## Architecture

```text
sentinel-gcc-simulator/
  backend/
    app/
      config.py
      settings.py
      security.py
      main.py
      schemas.py
      service.py
      connectors/
        world_monitor_connector.py
      engines/
        escalation_engine.py
        oil_simulator.py
        disruption_model.py
        financial_model.py
        news_intelligence.py
        advisory_engine.py
        advisor_chat_engine.py
    tests/
      test_api.py
      test_service.py
    scripts/
      generate_scenario_matrix.py
  frontend/
    streamlit_app.py
  output/
    scenario_matrix.json
    scenario_matrix.csv
  docker-compose.yml
  .env.example
```

## Local run (recommended)

### 1) Backend

```bash
cd /Users/kamal/Documents/Playground/sentinel-gcc-simulator/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional secure mode
export SENTINEL_API_KEYS="secure-demo-key"
export SENTINEL_ALLOWED_ORIGINS="http://localhost:8501,http://127.0.0.1:8501"
export SENTINEL_ENABLE_API_NEWS_SOURCES="true"

# Optional API keys for broad leading-channel coverage
export SENTINEL_NEWSAPI_KEY=""
export SENTINEL_GNEWS_KEY=""
export SENTINEL_GUARDIAN_KEY=""
export SENTINEL_NYT_KEY=""
export SENTINEL_MEDIASTACK_KEY=""
export SENTINEL_LIVE_QUERY="Strait of Hormuz OR GCC oil export OR LNG shipping disruption"
export SENTINEL_ENABLE_AI_ADVISOR="true"
export SENTINEL_OPENAI_API_KEY=""
export SENTINEL_OPENAI_MODEL="gpt-4.1-mini"
export SENTINEL_OPENAI_BASE_URL="https://api.openai.com/v1"

uvicorn app.main:app --reload --port 8000
```

Backend endpoints:
- `GET /health`
- `GET /meta/tiers`
- `POST /simulate`
- `GET /intel/live`
- `POST /simulate/live`
- `POST /advisor/chat`
- `GET /learning/entries`
- `POST /learning/entries`

`/simulate`, `/simulate/live`, and `/advisor/chat` also accept optional `company_profile` overrides:
- `name`
- `daily_export_volume_bpd`
- `fiscal_break_even_price_usd_per_bbl`
- `debt_obligations_usd_bn`
- `insurance_dependency_ratio`

`/intel/live` query parameters:
- `lookback_hours` (6-168)
- `max_items` (10-200)
- `include_api_sources` (`true`/`false`)
- `providers` (repeatable, e.g. `providers=newsapi&providers=guardian` or `providers=all`)

### 2) Frontend

```bash
cd /Users/kamal/Documents/Playground/sentinel-gcc-simulator/frontend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export SENTINEL_BACKEND_URL="http://localhost:8000"
export SENTINEL_API_KEY="secure-demo-key"  # optional

streamlit run streamlit_app.py
```

Open Streamlit URL (typically `http://localhost:8501`).

In the sidebar, keep `Enable internet live feeds` enabled to include live news threads, signal extraction, and suggested response steps in every scenario run.
Use `Include API providers` and `Provider selection` to aggregate all configured sources at once.
The dashboard also includes a dedicated `World Monitor Connector Layer` panel for normalized events.
Use the `Sentinel Advisor Chat` tab for interactive, plain-language guidance tied to the selected scenario.
Use `Learning Lab` to feed outcomes/lessons so the advisor can reference prior mistakes and mitigations.

## Docker run

```bash
cd /Users/kamal/Documents/Playground/sentinel-gcc-simulator
cp .env.example .env
# adjust values in .env as needed

docker compose --env-file .env up --build
```

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:8501`

## Free cloud deploy (Render + Streamlit Community Cloud)

This repository includes a Render Blueprint file at `render.yaml` for the backend.

### 1) Deploy backend to Render (free)

1. Push this repo to GitHub.
2. In Render: New + -> Blueprint.
3. Select your GitHub repo and deploy.
4. Confirm the service uses:
   - build command: `pip install -r requirements.txt`
   - start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. After deploy, copy backend URL:
   - `https://<your-render-service>.onrender.com`

Quick check:

```bash
curl -sS https://<your-render-service>.onrender.com/health
```

### 2) Deploy frontend to Streamlit Community Cloud (free)

1. In Streamlit Community Cloud, create a new app from this repo.
2. Set the main file path to:
   - `frontend/streamlit_app.py`
3. In app settings -> Secrets, add:

```toml
SENTINEL_BACKEND_URL = "https://<your-render-service>.onrender.com"
SENTINEL_API_KEY = "secure-demo-key"
```

You can copy from `frontend/.streamlit/secrets.toml.example`.

### 3) Final connection hardening

The Blueprint starts with `SENTINEL_ALLOWED_ORIGINS="*"` so first connection works immediately.

After your Streamlit app URL is live, update Render env var:

```text
SENTINEL_ALLOWED_ORIGINS=https://<your-streamlit-app>.streamlit.app
```

If you rotate API key later, update both:
- Render: `SENTINEL_API_KEYS`
- Streamlit Secrets: `SENTINEL_API_KEY`

## Tests

```bash
cd /Users/kamal/Documents/Playground/sentinel-gcc-simulator/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
```

## Final output generation

Generate a deterministic scenario matrix across all tiers and durations:

```bash
cd /Users/kamal/Documents/Playground/sentinel-gcc-simulator/backend
python scripts/generate_scenario_matrix.py
```

This writes:
- `/Users/kamal/Documents/Playground/sentinel-gcc-simulator/output/scenario_matrix.json`
- `/Users/kamal/Documents/Playground/sentinel-gcc-simulator/output/scenario_matrix.csv`

## Notes for model extension

- All editable assumptions are centralized in `backend/app/config.py`
- Escalation logic and financial translation are cleanly separated in `backend/app/engines/`
- Trigger thresholds can be adjusted without modifying frontend code
- Live signal patterns can be edited in `backend/app/engines/news_intelligence.py` (`SIGNAL_RULES`)
