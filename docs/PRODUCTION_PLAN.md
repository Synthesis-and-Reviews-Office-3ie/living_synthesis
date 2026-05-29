# Production Deployment Plan

> **Last Updated:** January 1, 2026

## Product Vision

**Living Evidence Hub** - A home for living systematic reviews and evidence gap maps.

Teams can:
1. **Host their protocol** - Upload or link to PROSPERO registration
2. **Link original publication** - DOI/citation of the published SR/EGM
3. **Continuous monitoring** - Automated search for new evidence
4. **Track updates** - Version history of all changes
5. **Public landing page** - Shareable page showing living review status

---

## Progress Summary

| Phase | Status | Progress |
|-------|--------|----------|
| Phase 1: MVP | ✅ Complete | 100% |
| Phase 2: Beta | 🟡 In Progress | 65% |
| Phase 3: Launch | ⚪ Not Started | 0% |

---

## Feature Roadmap

### MVP (Complete ✅)
- [x] Multi-source search (OpenAlex, PubMed, arXiv, Crossref, GitHub, Google)
- [x] AI query generation from topic description
- [x] Smart incremental search (uses last_run_at, not full re-fetch)
- [x] Tier-based limits (search_days, max_papers, sources)
- [x] HITL review queue
- [x] Google OAuth authentication with tier sync
- [x] Dashboard with stats and navigation
- [ ] Protocol import (PICO → queries)
- [ ] Inclusion and exclusion criteria should be standalones so reviewers can signal which one.
- [ ] Citation export (RIS, BibTeX)

### Beta (Living Review Features) - In Progress
- [x] **Living Reviews CRUD** - Create, read, update, delete reviews
- [x] **Topic linking** - Link review to topic for paper source (bidirectional)
- [x] **PICO criteria** - Population, Intervention, Comparator, Outcomes fields
- [x] **Paper sync** - Sync papers from topic to screening queue
- [x] **Screening interface** - Include/Exclude/Maybe decisions
- [x] **Screening stats** - Total, pending, included, conflicts counts
- [x] **Registry IDs** - PROSPERO, OSF, Cochrane, Campbell fields
- [x] **PDF viewer** - View PDFs for open access papers (arXiv, Unpaywall)
- [ ] **Protocol hosting** - Upload PDF or link to PROSPERO/OSF
- [ ] **Original publication** - Link DOI, auto-fetch citation
- [ ] **Public landing page** - `app.com/reviews/your-review-slug`
- [ ] **Version snapshots** - "Update #3: Added 12 studies, excluded 45"
- [ ] **PRISMA flow generator** - Auto-update diagram with each run
- [ ] **AI-assisted screening** - AI: Include/Exclude/Maybe + rationale
- [ ] **Dual screening** - Assign papers to team members
- [ ] **Conflict resolution** - Third reviewer arbitration

### Topic Enhancements (Research Discovery) - In Progress
- [x] **AI Paper Summaries** - LLM-generated 2-3 sentence summaries (tier-gated: Free 10, Pro 100, Team unlimited)
- [x] **Topic Analytics Dashboard** - Stats cards: Total Papers, New This Week, AI Summaries, Top Source
- [x] **Rich Paper Cards** - Visual cards with AI summary, relevance score (X/10), source badge
- [x] **Google Scholar Integration** - Added as source with simple keyword queries (scholarly package)
- [x] **Pagination for All Sources** - OpenAlex cursor, PubMed batch, arXiv offset, Crossref offset
- [x] **Removed Tier Restrictions** - All bibliographic sources available to all tiers
- [x] **LLM Relevance Filtering** - AI scores papers 0-10 for relevance, filters noise (color-coded badges, hide low relevance toggle)
- [x] **Smart Filters** - Filter by date, source, methods, open access
- [x] **Weekly AI Digest** - Auto-generated narrative summary of new papers
- [ ] **Hot Papers Detection** - Flag papers with unusual citation velocity
- [ ] **Export to Reference Managers** - RIS/BibTeX export for Zotero/Mendeley

### Launch (Integrations)
- [ ] **Citation chasing** - Forward/backward from included studies
- [ ] **Full-text retrieval** - Unpaywall/OA sources
- [ ] **Tool export** - Covidence, EPPI-Reviewer, Rayyan formats
- [ ] **Synthesis alerts** - "New RCT may change your conclusions"
- [ ] **Risk of Bias** - RoB2, ROBINS-I templates
- [ ] **Registry linking** - PROSPERO, Campbell, Cochrane updates

---

## 1. Infrastructure Components

### Compute (Choose one)
| Option | Monthly Cost | Pros | Cons |
|--------|-------------|------|------|
| **Railway** | ~$20-50 | Easy, auto-scaling | Limited customization |
| **Render** | ~$25-75 | Good free tier, simple | Can be slow |
| **AWS (ECS/Lambda)** | ~$50-200 | Full control, scalable | Complex setup |
| **Fly.io** | ~$20-50 | Edge deployment, fast | Smaller ecosystem |

### Database
- **PostgreSQL** (Supabase free tier → $25/mo paid)
- Tables: `users`, `subscriptions`, `papers`, `newsletters`, `review_queue`

### Queue & Cache
- **Redis** (Upstash free tier → $10/mo)
- Used for: Celery task queue, rate limiting, caching API responses

### File Storage
- **Cloudflare R2** (free 10GB) or **AWS S3** (~$5/mo)
- Store: Newsletter HTML/PDF archives, images

### Email Delivery
- **Resend** (free 3k/mo → $20/mo for 50k)
- **SendGrid** (free 100/day → $20/mo)

---

## 2. Multi-Tenancy Architecture

### User Tiers
```
FREE TIER:
- 1 topic (e.g., "LLMs in Evidence Synthesis")
- Weekly email digest
- Last 4 newsletters in archive
- Sources: All 6 (OpenAlex, PubMed, arXiv, Crossref, GitHub, Google Scholar)
- Unlimited papers/source with pagination
- 30-day fixed lookback
- 10 AI summaries per topic

PRO ($29/mo):
- 3 custom topics
- Daily or weekly frequency
- Full archive access
- API access
- Custom RSS export
- Sources: All 6 with pagination
- 7-365 day configurable lookback
- 100 AI summaries per topic

TEAM ($99/mo):
- 10 topics
- Team collaboration (HITL review)
- Custom branding
- Slack/Teams integration
- Priority support
- Sources: All 6 with pagination
- 7-365 day configurable lookback
- Smart incremental search (uses last_run_at + 2-day buffer)
- Unlimited AI summaries
```

### Tier Feature Matrix
| Feature | Free | Pro | Team |
|---------|------|-----|------|
| Topics | 1 | 3 | 10 |
| Sources | 6 (all) | 6 (all) | 6 (all) |
| Papers/Source | Unlimited | Unlimited | Unlimited |
| Pagination | ✅ | ✅ | ✅ |
| AI Summaries | 10/topic | 100/topic | Unlimited |
| Search Days | 30 (fixed) | 7-365 | 7-365 |
| Incremental Search | ❌ | ❌ | ✅ |
| HITL Review | ❌ | ✅ | ✅ |
| API Access | ❌ | ✅ | ✅ |

### Database Schema (Multi-tenant)
```sql
-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    tier VARCHAR DEFAULT 'free',
    stripe_customer_id VARCHAR,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Topics (what users subscribe to)
CREATE TABLE topics (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    name VARCHAR NOT NULL,
    queries JSONB NOT NULL,  -- {openalex: "...", pubmed: "...", arxiv: "...", ...}
    frequency VARCHAR DEFAULT 'weekly',
    is_active BOOLEAN DEFAULT true,
    search_days INTEGER DEFAULT 30,  -- Lookback period (Pro/Team: 7-365)
    max_papers_per_source INTEGER DEFAULT 50,  -- Free: 50, Pro: 200, Team: 500
    last_run_at TIMESTAMP  -- Used for smart incremental search
);

-- Papers (deduplicated across all users)
CREATE TABLE papers (
    id UUID PRIMARY KEY,
    doi VARCHAR UNIQUE,
    title VARCHAR NOT NULL,
    abstract TEXT,
    source VARCHAR,
    publication_date DATE,
    oa_url VARCHAR,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Paper Analysis (per topic, since relevance varies)
CREATE TABLE paper_analysis (
    id UUID PRIMARY KEY,
    paper_id UUID REFERENCES papers(id),
    topic_id UUID REFERENCES topics(id),
    headline VARCHAR,
    summary TEXT,
    category VARCHAR,
    relevance_score INTEGER,
    include BOOLEAN DEFAULT true,  -- HITL decision
    reviewed_at TIMESTAMP
);

-- Newsletters (generated output)
CREATE TABLE newsletters (
    id UUID PRIMARY KEY,
    topic_id UUID REFERENCES topics(id),
    html_url VARCHAR,
    pdf_url VARCHAR,
    sent_at TIMESTAMP,
    open_rate FLOAT,
    click_rate FLOAT
);

-- Living Review (the "home" for an SR/EGM)
CREATE TABLE living_reviews (
    id UUID PRIMARY KEY,
    topic_id UUID REFERENCES topics(id),  -- Links to search config
    
    -- Protocol & Publication
    title VARCHAR NOT NULL,  -- "Effects of X on Y: A Living Systematic Review"
    slug VARCHAR UNIQUE,  -- URL: /reviews/effects-of-x-on-y
    protocol_url VARCHAR,  -- PROSPERO, OSF link
    protocol_file_url VARCHAR,  -- Uploaded PDF
    publication_doi VARCHAR,  -- DOI of original paper
    publication_citation TEXT,  -- Full citation
    
    -- Registration
    prospero_id VARCHAR,  -- CRD42024xxxxxx
    cochrane_id VARCHAR,
    campbell_id VARCHAR,
    
    -- Status
    status VARCHAR DEFAULT 'active',  -- active, paused, completed, archived
    is_public BOOLEAN DEFAULT false,  -- Show on public page?
    
    -- Eligibility Criteria (for AI screening)
    pico_population TEXT,
    pico_intervention TEXT,
    pico_comparator TEXT,
    pico_outcome TEXT,
    inclusion_criteria JSONB,  -- [{criterion: "RCTs only", required: true}, ...]
    exclusion_criteria JSONB,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP,
    last_update_version INTEGER DEFAULT 0
);

-- Update Versions (track each update cycle)
CREATE TABLE review_updates (
    id UUID PRIMARY KEY,
    living_review_id UUID REFERENCES living_reviews(id),
    version INTEGER NOT NULL,  -- 1, 2, 3...
    
    -- What changed
    papers_screened INTEGER DEFAULT 0,
    papers_included INTEGER DEFAULT 0,
    papers_excluded INTEGER DEFAULT 0,
    
    -- Artifacts
    prisma_flow_url VARCHAR,  -- Generated PRISMA diagram
    change_summary TEXT,  -- "Added 3 RCTs from 2024"
    
    -- Timing
    search_date TIMESTAMP,
    published_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Team Members (for collaboration)
CREATE TABLE review_team (
    id UUID PRIMARY KEY,
    living_review_id UUID REFERENCES living_reviews(id),
    user_id UUID REFERENCES users(id),
    role VARCHAR DEFAULT 'screener',  -- owner, admin, screener, viewer
    invited_at TIMESTAMP DEFAULT NOW(),
    accepted_at TIMESTAMP
);
```

---

## 3. API Endpoints

```python
# FastAPI routes

# Auth
POST   /api/auth/signup
POST   /api/auth/login
POST   /api/auth/logout

# Topics (Search Configuration)
GET    /api/topics                    # List user's topics
POST   /api/topics                    # Create new topic
PUT    /api/topics/{id}               # Update topic queries
DELETE /api/topics/{id}
POST   /api/topics/{id}/run           # Run paper search

# Review Queue (HITL Screening)
GET    /api/topics/{id}/review        # Get pending papers for review
PUT    /api/topics/{id}/review        # Submit review decisions
POST   /api/topics/{id}/generate      # Force generate newsletter

# Living Reviews (SR/EGM Home)
GET    /api/reviews                   # List user's living reviews
POST   /api/reviews                   # Create new living review
GET    /api/reviews/{id}              # Get review details
PUT    /api/reviews/{id}              # Update review metadata
DELETE /api/reviews/{id}

# Protocol & Publication
POST   /api/reviews/{id}/protocol     # Upload protocol PDF
PUT    /api/reviews/{id}/publication  # Set original publication DOI
PUT    /api/reviews/{id}/pico         # Update PICO criteria

# Screening
GET    /api/reviews/{id}/screening    # Get papers to screen
POST   /api/reviews/{id}/screening    # Submit screening decisions
GET    /api/reviews/{id}/conflicts    # Get conflicting decisions
POST   /api/reviews/{id}/resolve      # Resolve conflicts

# Update Versions
GET    /api/reviews/{id}/updates      # List all update versions
POST   /api/reviews/{id}/updates      # Publish new update
GET    /api/reviews/{id}/updates/{v}  # Get specific update details
GET    /api/reviews/{id}/prisma       # Get current PRISMA flow

# Team Collaboration
GET    /api/reviews/{id}/team         # List team members
POST   /api/reviews/{id}/team         # Invite team member
PUT    /api/reviews/{id}/team/{uid}   # Update role
DELETE /api/reviews/{id}/team/{uid}   # Remove from team

# Public Page (no auth required)
GET    /reviews/{slug}                # Public landing page
GET    /reviews/{slug}/updates        # Public update history
GET    /reviews/{slug}/included       # List of included studies

# Export
GET    /api/reviews/{id}/export/ris   # Export as RIS
GET    /api/reviews/{id}/export/bib   # Export as BibTeX
GET    /api/reviews/{id}/export/csv   # Export as CSV

# Newsletters
GET    /api/topics/{id}/newsletters   # List past newsletters
GET    /api/newsletters/{id}          # Get specific newsletter
GET    /api/newsletters/{id}/html     # Get HTML content

# Subscription
POST   /api/subscribe                 # Email signup
DELETE /api/unsubscribe/{token}

# Billing (Stripe)
POST   /api/billing/checkout          # Create checkout session
POST   /api/billing/webhook           # Stripe webhook
GET    /api/billing/portal            # Customer portal link
```

---

## 4. Background Jobs (Celery)

```python
# tasks.py

@celery.task
def run_weekly_ingestion():
    """Runs every Sunday at 6 AM UTC"""
    for topic in Topic.query.filter_by(is_active=True, frequency='weekly'):
        ingest_for_topic.delay(topic.id)

@celery.task
def ingest_for_topic(topic_id):
    """Fetch papers for a specific topic"""
    topic = Topic.query.get(topic_id)
    
    # 1. Fetch from all sources
    papers = fetch_all_sources(topic.queries)
    
    # 2. Deduplicate
    papers = deduplicate(papers)
    
    # 3. Pre-filter
    papers = prefilter(papers)
    
    # 4. Analyze with LLM
    analyzed = analyze_papers(papers, topic)
    
    # 5. Queue for review (or auto-publish for free tier)
    if topic.user.tier == 'free':
        generate_newsletter.delay(topic.id)
    else:
        notify_review_ready.delay(topic.id)

@celery.task
def generate_newsletter(topic_id):
    """Generate and send newsletter"""
    topic = Topic.query.get(topic_id)
    
    # Get reviewed papers
    papers = get_approved_papers(topic_id)
    
    # Generate HTML
    html = render_newsletter(papers, topic)
    
    # Upload to S3
    url = upload_to_s3(html, topic_id)
    
    # Send email
    send_newsletter_email(topic.user.email, html)
    
    # Track
    Newsletter.create(topic_id=topic_id, html_url=url)

# Celery Beat Schedule
CELERYBEAT_SCHEDULE = {
    'weekly-ingestion': {
        'task': 'tasks.run_weekly_ingestion',
        'schedule': crontab(hour=6, minute=0, day_of_week=0),  # Sunday 6 AM
    },
}
```

---

## 5. Deployment Steps

### Phase 1: MVP (Week 1-2)

#### 1. Set up infrastructure
- [ ] Railway project with PostgreSQL + Redis
- [ ] Cloudflare R2 bucket
- [ ] Resend account

#### 2. Refactor current code
- [x] Move from SQLite to PostgreSQL (supports both, SQLite for dev/tests)
- [x] Add user authentication (JWT + bcrypt)
- [x] Add Celery for background jobs (configured, tasks defined)
- [x] Create basic FastAPI endpoints
  - [x] Auth: signup, login, profile, password reset
  - [x] Topics: CRUD with tier limits
  - [x] Subscriptions: subscribe/unsubscribe
  - [x] Health checks
- [x] API rate limiting (slowapi + Redis)
- [x] Email service integration (Resend)
- [x] S3/R2 storage service
- [x] Error monitoring (Sentry integration)
- [x] Unit tests (24 passing)
- [x] CI/CD pipeline (GitHub Actions)
- [x] Docker support (Dockerfile + docker-compose)

#### 3. Simple frontend
- [x] Landing page with pricing
- [x] Login / Signup / Password reset pages
- [x] Dashboard with stats
- [x] Topics list and create pages
- [x] Settings page with profile & billing
- [x] Review queue UI (HITL)
- [x] Living Reviews list, create, and detail pages
- [x] Paper screening interface (Include/Exclude/Maybe)
- [x] Topic linking UI in review detail page

### Phase 2: Beta (Week 3-4)

#### 4. Add multi-tenancy
- [x] Topic creation UI
- [x] Query builder interface  
- [x] Review queue UI
- [x] Living Reviews backend (models, schemas, API)
- [x] Screening queue with paper sync
- [ ] Team collaboration (invite members, roles)
- [ ] Conflict resolution workflow

#### 5. Add billing
- [x] Stripe integration (backend ready)
- [ ] Checkout flow UI
- [ ] Subscription management UI
- [x] Usage limits (enforced in API)

#### 6. Monitoring
- [x] Sentry for errors (integrated)
- [ ] PostHog for analytics

### Phase 3: Launch (Week 5-6)

#### 7. Polish
- [ ] Email templates (HTML)
- [ ] Onboarding flow
- [ ] Documentation

#### 8. Marketing
- [ ] Product Hunt launch
- [ ] Twitter/LinkedIn posts
- [ ] Academic forums (Cochrane, Campbell)

---

## 6. Cost Estimate (Monthly)

### At 100 users (mostly free)
| Service | Cost |
|---------|------|
| Railway (compute) | $20 |
| Supabase (database) | $0 (free tier) |
| Upstash Redis | $0 (free tier) |
| Cloudflare R2 | $0 (free tier) |
| Resend (email) | $0 (free tier) |
| OpenRouter (LLM) | ~$50 |
| Domain | $12/year |
| **Total** | **~$70/mo** |

### At 1,000 users (10% paid)
| Service | Cost |
|---------|------|
| Railway | $50 |
| Supabase | $25 |
| Upstash Redis | $10 |
| Cloudflare R2 | $5 |
| Resend | $20 |
| OpenRouter | ~$300 |
| **Total** | **~$410/mo** |
| **Revenue** (100 × $29) | **$2,900/mo** |
| **Profit** | **~$2,500/mo** |

---

## 7. Security Considerations

- [x] API rate limiting (per user) - slowapi with Redis
- [ ] Input sanitization (query injection)
- [x] Secrets in environment variables (not in code!) - .env + pydantic-settings
- [ ] HTTPS everywhere (need deployment)
- [ ] GDPR compliance (data export/deletion)
- [ ] SOC 2 if targeting enterprise

---

## 8. Scaling Considerations

### When to scale:
- **100+ concurrent LLM calls**: Add worker replicas
- **10k+ papers/week**: Add read replicas for DB
- **Email deliverability issues**: Consider dedicated IP

### Future features:
- [ ] Slack/Teams integration
- [ ] Custom domains for white-label
- [ ] API for programmatic access
- [ ] PDF export
- [ ] Collaborative HITL review
- [ ] AI-assisted query builder
