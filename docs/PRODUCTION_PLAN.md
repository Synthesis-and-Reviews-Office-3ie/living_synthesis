# Production Deployment Plan

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

PRO ($29/mo):
- 3 custom topics
- Daily or weekly frequency
- Full archive access
- API access
- Custom RSS export

TEAM ($99/mo):
- 10 topics
- Team collaboration (HITL review)
- Custom branding
- Slack/Teams integration
- Priority support
```

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
    queries JSONB NOT NULL,  -- {openalex: "...", pubmed: "...", google: "..."}
    frequency VARCHAR DEFAULT 'weekly',
    is_active BOOLEAN DEFAULT true
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
```

---

## 3. API Endpoints

```python
# FastAPI routes

# Auth
POST   /api/auth/signup
POST   /api/auth/login
POST   /api/auth/logout

# Topics
GET    /api/topics                    # List user's topics
POST   /api/topics                    # Create new topic
PUT    /api/topics/{id}               # Update topic queries
DELETE /api/topics/{id}

# Review Queue (HITL)
GET    /api/topics/{id}/review        # Get pending papers for review
PUT    /api/topics/{id}/review        # Submit review decisions
POST   /api/topics/{id}/generate      # Force generate newsletter

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
```bash
# 1. Set up infrastructure
- Railway project with PostgreSQL + Redis
- Cloudflare R2 bucket
- Resend account

# 2. Refactor current code
- Move from SQLite to PostgreSQL
- Add user authentication (Auth.js or Supabase Auth)
- Add Celery for background jobs
- Create basic FastAPI endpoints

# 3. Simple frontend
- Landing page with waitlist signup
- Basic dashboard to view newsletters
```

### Phase 2: Beta (Week 3-4)
```bash
# 4. Add multi-tenancy
- Topic creation UI
- Query builder interface
- Review queue UI

# 5. Add billing
- Stripe integration
- Subscription management
- Usage limits

# 6. Monitoring
- Sentry for errors
- PostHog for analytics
```

### Phase 3: Launch (Week 5-6)
```bash
# 7. Polish
- Email templates
- Onboarding flow
- Documentation

# 8. Marketing
- Product Hunt launch
- Twitter/LinkedIn posts
- Academic forums (Cochrane, Campbell)
```

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

- [ ] API rate limiting (per user)
- [ ] Input sanitization (query injection)
- [ ] Secrets in environment variables (not in code!)
- [ ] HTTPS everywhere
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
