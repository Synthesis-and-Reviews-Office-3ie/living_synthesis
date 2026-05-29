# Living Evidence

An AI-assisted platform for tracking, synthesizing, and publishing research at the intersection of **Large Language Models (LLMs)** and **Evidence Synthesis**. The project has two complementary surfaces:

1. **A standalone Python pipeline** that scans scholarly sources and produces a weekly Markdown/HTML newsletter.
2. **A full SaaS application** (FastAPI backend + Next.js frontend) that adds user accounts, topic subscriptions, a human-in-the-loop review workflow, "living reviews", billing, and scheduled background jobs.

---

## Repository layout

```
.
├── main.py                     # CLI entry point: runs the newsletter pipeline end-to-end
├── regenerate_html.py          # Re-renders an existing newsletter draft to HTML
├── run_retrospective.py        # Backfill / retrospective newsletter generation
├── create_tables.py            # Ad-hoc DB bootstrap scripts
├── create_living_reviews_table.py
├── create_workflow_tables.py
├── add_columns.py
├── alembic.ini                 # Alembic migration config
├── alembic/                    # SQLAlchemy migration scripts
├── docker-compose.yml          # Postgres + Redis + API + Celery worker + Celery beat
├── Dockerfile
├── requirements.txt
│
├── config/
│   └── settings.yaml           # Pipeline config (API keys, LLM model, DB connection)
│
├── src/                        # Standalone newsletter pipeline (used by main.py)
│   ├── ingestion/              # OpenAlex, PubMed, Crossref, arXiv, GitHub, Google, RSS fetchers
│   ├── processing/             # Deduplication and Unpaywall open-access enrichment
│   ├── analysis/               # LLM-based classification, extraction, summarization
│   ├── presentation/           # HTML rendering for the newsletter
│   ├── storage/                # Postgres / in-memory storage layer for the pipeline
│   └── utils/
│
├── app/                        # FastAPI SaaS backend
│   ├── main.py                 # FastAPI app, CORS, Sentry, rate limiting, router wiring
│   ├── config.py               # Pydantic settings (env-driven)
│   ├── database.py             # SQLAlchemy engine / session / init_db
│   ├── models.py               # ORM models (users, topics, papers, reviews, subscriptions, …)
│   ├── schemas.py              # Pydantic request/response schemas
│   ├── auth.py                 # JWT auth, password hashing
│   ├── tasks.py                # Celery tasks + beat schedule (ingestion, newsletter sending)
│   ├── routers/
│   │   ├── auth.py             # Signup, login, password reset
│   │   ├── topics.py           # User-defined research topics
│   │   ├── papers.py           # Paper listing / search
│   │   ├── review.py           # Reviewer screening of papers
│   │   ├── workflow.py         # Multi-reviewer assignment & conflict resolution
│   │   ├── living_reviews.py   # Living systematic review management
│   │   ├── newsletters.py      # Newsletter rendering & sending
│   │   ├── ai.py               # LLM-backed endpoints (summarize, classify, etc.)
│   │   ├── subscriptions.py    # Plan tiers
│   │   └── billing.py          # Stripe checkout / webhooks
│   └── services/
│       ├── llm.py              # LLM client wrapper (OpenRouter / OpenAI)
│       ├── email.py            # Transactional email via Resend
│       ├── pdf_fetcher.py      # PDF retrieval helpers
│       └── storage.py          # S3 / local file storage
│
├── frontend/                   # Next.js app (App Router, TypeScript, Tailwind)
│   ├── src/app/                # Routes: dashboard, topics, reviews, settings, login, signup, …
│   ├── src/components/         # Dashboard layout, review panels, shadcn/ui components
│   └── src/lib/                # API client, helpers
│
├── templates/
│   └── newsletter.html         # Jinja2 template for the rendered newsletter
│
├── tests/                      # pytest suite (auth, health, topics, …)
├── data/                       # Local data outputs
└── docs/
    └── PRODUCTION_PLAN.md
```

---

## Part 1 — Newsletter pipeline (CLI)

Automates a weekly digest of LLM × evidence-synthesis research.

### Features

- **Multi-source ingestion**: OpenAlex, PubMed, Crossref, arXiv, GitHub, Google Custom Search, and RSS feeds.
- **Smart deduplication**: merges records by DOI.
- **Open-access discovery**: PDF links resolved via the Unpaywall API.
- **LLM editor** (via OpenRouter / OpenAI):
    - Practitioner-focused headlines and "so what?" summaries.
    - Category tagging (`New Tool/App`, `Methodology`, `Review/Benchmark`, `Opinion/Discussion`).
    - Mentioned model extraction (e.g. GPT-4, Llama 3).
    - Relevance scoring to filter noise.
- **Markdown + HTML output** ready to publish (Substack-style).

### Setup

1. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
2. Edit [config/settings.yaml](config/settings.yaml):
    - OpenRouter / OpenAI API key.
    - Email for Unpaywall (required).
    - Optional: OpenAlex / PubMed keys, Google Custom Search key + CX, GitHub token.
    - Optional: Postgres `connection_string` (defaults to in-memory).
3. Run the pipeline:
    ```bash
    python main.py
    ```

> **Note:** Google Scholar has no official API. Twitter/X content is fetched indirectly through Google site-restricted search.

### Output

- `newsletter_draft.md` — Markdown draft, grouped by category and sorted by relevance.
- `newsletter_<date>.html` — rendered HTML (see [regenerate_html.py](regenerate_html.py) to re-render).

---

## Part 2 — SaaS application (FastAPI + Next.js)

A multi-tenant web app that turns the pipeline into a product: users define research topics, the system ingests and screens papers on a schedule, reviewers triage results, and approved items flow into newsletters or "living reviews".

### Backend ([app/](app/))

- **FastAPI** with router-based modular layout (see [app/routers/](app/routers/)).
- **SQLAlchemy 2.0** ORM, **Alembic** migrations.
- **JWT auth** (`python-jose`, `passlib[bcrypt]`).
- **Celery + Redis** for background ingestion and scheduled newsletter sending ([app/tasks.py](app/tasks.py)).
- **Stripe** subscriptions and **Resend** transactional email.
- **Sentry** error monitoring and **slowapi** rate limiting.
- Optional **S3** storage for PDFs (`boto3`).

### Frontend ([frontend/](frontend/))

- **Next.js** (App Router) + **TypeScript** + **Tailwind CSS** + **shadcn/ui**.
- Pages: dashboard, topics, reviews, settings, auth (login / signup / forgot password).
- Components for multi-reviewer assignment and conflict resolution.

### Running with Docker

The simplest way to bring up the full stack (Postgres + Redis + API + Celery worker + Celery beat):

```bash
cp .env.example .env   # fill in secrets (DB URL is set by compose; add API/LLM/Stripe/Resend keys)
docker compose up --build
```

Services:

| Service         | Port | Purpose                              |
| --------------- | ---- | ------------------------------------ |
| `db`            | 5432 | PostgreSQL 16                        |
| `redis`         | 6379 | Broker for Celery, rate-limit store  |
| `api`           | 8000 | FastAPI (`uvicorn app.main:app`)     |
| `celery_worker` | —    | Background task processing           |
| `celery_beat`   | —    | Scheduled tasks                      |

API docs: <http://localhost:8000/docs>

### Running locally without Docker

```bash
# 1. Backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# 2. Worker + scheduler (in separate shells)
celery -A app.tasks worker --loglevel=info
celery -A app.tasks beat --loglevel=info

# 3. Frontend
cd frontend
npm install
npm run dev
```

### Environment variables

The backend reads configuration from environment variables / `.env` (see [app/config.py](app/config.py)). Common keys:

- `DATABASE_URL`, `REDIS_URL`
- `SECRET_KEY` (JWT signing)
- `OPENAI_API_KEY` / OpenRouter base URL
- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`
- `RESEND_API_KEY`, sender address
- `SENTRY_DSN` (optional)
- `AWS_*` (optional, for S3)

### Tests

```bash
pytest
```

---

## License

MIT
