# Support Insight

An AI-powered customer support analytics platform. Upload a CSV of support tickets and get instant dashboards, trend analysis, category breakdowns, sentiment scoring, revenue risk tracking, and AI-generated agent replies — all in a fully responsive web app.
<img width="1914" height="996" alt="image" src="https://github.com/user-attachments/assets/c38da325-6166-43a2-814b-ed77b4efca6b" />


---

## Key Features

### Analytics & Dashboards
- **KPI Overview** — Total tickets, open/resolved/escalated counts, resolution rate, escalation rate, average sentiment score, revenue at risk, and tickets processed today
- **Tickets by Category** — Horizontal bar chart showing ticket volume across all 8 support categories
- **Sentiment Distribution** — Donut chart breaking down positive / neutral / frustrated / angry tickets
- **Revenue at Risk** — Bar chart showing unresolved ticket order values by category, so you know which problems are costing the most
- **Top Issues** — Most frequently occurring specific problems across all tickets (e.g. "late delivery", "double charge")
- **Top Countries** — Geographic breakdown of ticket volume
- **Category Radar** — Radar chart comparing ticket volume vs revenue at risk per category at a glance
- **Top Products** — Which products generate the most support tickets

### Trends
- **Daily Ticket Volume** — Area chart showing ticket flow over time
- **Sentiment Over Time** — Line chart tracking average sentiment score day by day
- **Daily Status Breakdown** — Stacked bar showing open/resolved/escalated per day
- **Volume vs Revenue at Risk** — Combined bar + line chart showing both metrics on the same timeline
- **Category Velocity** — Compares ticket count this period vs the previous period for each category, flagging what's increasing or decreasing
<img width="1916" height="992" alt="image" src="https://github.com/user-attachments/assets/d21c8b77-82ca-4265-b638-d8e052d6f28e" />

### Categories
- Stacked bar chart showing open / resolved / escalated tickets per category
- Clickable category cards showing percentage share, resolution rate, mini status bar
- Per-category drilldown with status donut, sentiment donut, and top issues bar chart
<img width="1915" height="996" alt="image" src="https://github.com/user-attachments/assets/2f7ed92e-6439-40d8-a9c1-e525fdb8437a" />

### Ticket Explorer
- Full-text search across all ticket messages
- Filter by category, channel, resolution status, sentiment label
- Sort by newest, oldest, most angry, or highest order value
- Expand any ticket to see the full message, agent reply, key issues, and metadata
- **Resolve** or **Escalate** tickets directly from the UI
- **Generate AI Reply** — uses Google Gemini to write a professional, empathetic agent response
<img width="1916" height="1000" alt="image" src="https://github.com/user-attachments/assets/24f60e1f-c824-4a23-b62b-b9bd86ef5fd5" />

### Upload
- Drag-and-drop CSV upload
- Automatic category inference from message keywords
- Automatic sentiment scoring per category
- Duplicate ticket detection — re-uploading the same file skips already-stored tickets
- Live upload progress indicator

### Navigation
- Collapsible sidebar on desktop — click the app icon to open, chevron to collapse
- Slide-out drawer on mobile with backdrop
- All filters (date range, channel, category) apply across all charts simultaneously

---

## How the Data Pipeline Works

When you upload a CSV, each ticket goes through this processing pipeline synchronously before being stored:

```
CSV Upload
    │
    ▼
1. Parse & Validate
   • Checks required columns: timestamp, customer_id, channel, message
   • Decodes UTF-8 or Latin-1 encoding automatically
   • Skips duplicate ticket_ids already in the database
    │
    ▼
2. Category Inference  (_infer_category)
   • Scans the message text (lowercased) for keywords
   • Each of 8 categories has a keyword list (e.g. "refund", "return" → Returns & Refunds)
   • Scores every category by keyword hit count
   • Assigns the highest-scoring category, falls back to "Other" if no keywords match
   • If the CSV already has a category column, that value is used directly
    │
    ▼
3. Subcategory Assignment
   • Each category has a list of subcategories (e.g. Billing → Duplicate Charge, Promo Code…)
   • One subcategory is randomly selected from the category's pool
    │
    ▼
4. Sentiment Scoring  (_make_ai_fields)
   • Each category has a calibrated mean (μ) and standard deviation (σ) based on
     how negative that type of complaint typically is:
       Customer Service  μ=1.8  (most negative — rude agent, unresolved issues)
       Product Quality   μ=2.3
       Billing & Payment μ=2.5
       Returns & Refunds μ=2.6
       Shipping          μ=2.8
       Account & Login   μ=2.9
       Technical Support μ=3.0
   • A score 1–5 is drawn from a Gaussian distribution: score = clamp(round(gauss(μ, σ)), 1, 5)
   • Score is mapped to a sentiment label:
       1–2 → positive
         3 → frustrated
       4–5 → angry
    │
    ▼
5. Key Issues Tagging
   • Each category has a pool of specific known issues
     (e.g. Shipping → ["late delivery", "missing package", "wrong address", …])
   • 1–3 issues are randomly sampled from the pool and stored as a JSON array
    │
    ▼
6. Store in SQLite
   • All fields saved to the tickets table
   • Indexes on timestamp, customer_id, category, and product for fast queries
```

### How Insights Are Calculated

All charts are generated at query time — no pre-aggregation. Each API endpoint runs a SQLAlchemy query with optional filters (category, days, channel) applied:

| Insight | How it's computed |
|---|---|
| **KPI Summary** | `COUNT`, `AVG(sentiment_score)`, `SUM(order_value)` where status ≠ resolved |
| **Tickets by Category** | `GROUP BY category ORDER BY COUNT DESC` |
| **Sentiment Distribution** | `GROUP BY sentiment_label`, counts per label |
| **Revenue at Risk** | `SUM(order_value)` where status ≠ resolved, grouped by category |
| **Top Issues** | Flattens the `key_issues` JSON array across all tickets, counts frequency per issue string |
| **Top Countries** | `GROUP BY customer_country ORDER BY COUNT DESC` |
| **Trends** | `GROUP BY DATE(timestamp)` — one row per day with ticket count, avg sentiment, status counts, revenue |
| **Velocity** | Compares `COUNT` in current N days vs previous N days per category, computes % change |
| **Category Radar** | Same as categories query, picks top 6 and maps count + revenue for radar axes |

### AI Reply Generation (Gemini)

When you click **Generate AI Reply** on a ticket, the message is sent to Google Gemini 2.0 Flash with a system prompt instructing it to write a professional, empathetic 2–4 sentence agent response. The category is included as context. The reply is saved back to the ticket so it only needs to be generated once. If Gemini is unavailable or no API key is set, a polite fallback message is returned.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite 5, Tailwind CSS 3, Recharts, Axios |
| Backend | FastAPI, SQLAlchemy 2, SQLite |
| AI | Google Gemini 2.0 Flash |
| Deployment | Docker (multi-stage), Render |

---

## Local Development

### Prerequisites
- Python 3.11+
- Node.js 18+

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/ticket-management-app.git
cd ticket-management-app
cp .env.example .env
```

### 2. Start the backend

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

Backend: `http://localhost:8000`  
API docs: `http://localhost:8000/docs`

### 3. Start the frontend

```bash
cd react-frontend
npm install
npm run dev
```

Frontend: `http://localhost:3000`

### 4. Load sample data

Go to the **Upload** page and upload `data/raw/sample_1000.csv`.

---

## Deployment on Render (Free)

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → **New → Web Service** → connect your repo
3. Render auto-detects the `Dockerfile`
4. Set instance type to **Free**
5. Add environment variables:
   - `DATABASE_URL` → `sqlite:///./support_db.sqlite3`
   - `GEMINI_API_KEY` → your key (or leave blank)
6. Click **Create Web Service**

The `Dockerfile` builds React and bundles it into the FastAPI server — one URL for everything.

> **Note:** Free tier uses SQLite, so data resets on each redeploy. Re-upload the sample CSV after deploying.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./support_db.sqlite3` | Database connection |
| `GEMINI_API_KEY` | *(empty)* | Google Gemini key — for AI replies only |
| `GEMINI_MODEL` | `gemini-1.5-flash` | Gemini model name |

Get a free Gemini API key at [aistudio.google.com](https://aistudio.google.com/app/apikey).

---

## CSV Format

| Column | Required | Format | Notes |
|---|---|---|---|
| `timestamp` | Yes | `YYYY-MM-DD HH:MM:SS` | |
| `customer_id` | Yes | string | |
| `channel` | Yes | `chat` / `email` / `web` | |
| `message` | Yes | text | Customer's message — used for category inference |
| `ticket_id` | No | UUID | Auto-generated if missing |
| `agent_reply` | No | text | Existing agent reply |
| `product` | No | string | Product name |
| `order_value` | No | numeric | Order value in USD — used for revenue at risk |
| `customer_country` | No | string | Country name |
| `resolution_status` | No | `open` / `resolved` / `escalated` | Defaults to `open` |
| `category` | No | string | Auto-inferred from message if missing |

---

## Project Structure

```
ticket-management-app/
├── backend/
│   ├── api/routes/
│   │   ├── tickets.py      # Upload, list, resolve, escalate
│   │   ├── insights.py     # All chart data endpoints
│   │   ├── suggest.py      # AI reply generation
│   │   └── search.py       # Semantic search (optional)
│   ├── models/
│   │   ├── ticket.py       # SQLAlchemy ticket model
│   │   ├── insight.py      # DailyInsight model
│   │   └── schemas.py      # Pydantic request/response schemas
│   ├── pipeline/
│   │   └── responder.py    # Gemini AI reply generation
│   ├── utils/
│   │   ├── gemini_client.py
│   │   └── logger.py
│   ├── db/session.py       # SQLAlchemy engine + session
│   ├── config.py           # App settings
│   └── main.py             # FastAPI app + static file serving
├── react-frontend/
│   └── src/
│       ├── pages/          # Dashboard, Trends, Categories, TicketExplorer, Upload
│       ├── components/     # Navbar, MetricCard, Badge, Spinner, SectionHeader
│       └── api/client.js   # Axios API client
├── data/raw/
│   └── sample_1000.csv     # 1000-row sample dataset
├── Dockerfile              # Multi-stage build (Node → Python)
├── render.yaml             # One-click Render deployment
└── .env.example            # Environment variable template
```
