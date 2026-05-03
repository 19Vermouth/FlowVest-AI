# FlowVest AI — Production Deployment Guide

This guide covers deploying FlowVest AI v2.0 to production environments.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Production Stack                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐   │
│  │   Cloud     │     │   Cloud     │     │   Cloud     │   │
│  │   Run /     │     │   Run /     │     │   Run /     │   │
│  │   K8s       │     │   K8s       │     │   K8s       │   │
│  │  (Backend)  │     │  (Celery)   │     │  (Frontend) │   │
│  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘   │
│         │                   │                   │          │
│         └───────────────────┼───────────────────┘          │
│                             │                               │
│              ┌──────────────┼──────────────┐               │
│              │              │              │               │
│       ┌──────▼──────┐ ┌─────▼──────┐ ┌────▼────┐         │
│       │  Cloud SQL  │ │Cloud Redis │ │ Firebase│         │
│       │ (PostgreSQL)│ │  (Broker)  │ │  Auth   │         │
│       └─────────────┘ └────────────┘ └─────────┘         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## ☁️ Deployment Options

### Option 1: Google Cloud Platform (Recommended)

**Services:**
- **Backend + Celery**: Cloud Run (serverless containers)
- **Frontend**: Firebase Hosting or Cloud Run
- **Database**: Cloud SQL for PostgreSQL
- **Redis**: Cloud Memorystore for Redis
- **Auth**: Firebase Authentication
- **Monitoring**: Cloud Monitoring + Cloud Logging

**Estimated Cost** (10k portfolios/month):
- Cloud Run: ~$20-50/month
- Cloud SQL (PostgreSQL): ~$30/month
- Cloud Memorystore (Redis): ~$15/month
- Firebase Auth: Free (10k/month MAU)
- **Total**: ~$65-95/month

### Option 2: AWS

**Services:**
- **Backend + Celery**: ECS Fargate or App Runner
- **Frontend**: S3 + CloudFront
- **Database**: RDS for PostgreSQL
- **Redis**: ElastiCache for Redis
- **Auth**: Firebase Authentication (cross-cloud) or Cognito
- **Monitoring**: CloudWatch

**Estimated Cost**: ~$80-120/month

### Option 3: DigitalOcean / Render (Simpler, Lower Cost)

**Services:**
- **Backend + Celery**: DigitalOcean App Platform or Render Web Services
- **Frontend**: Vercel or Netlify
- **Database**: DigitalOcean Managed PostgreSQL or Render PostgreSQL
- **Redis**: DigitalOcean Managed Redis or Render Redis
- **Auth**: Firebase Authentication

**Estimated Cost**: ~$40-70/month

---

## 📦 Pre-Deployment Checklist

### 1. Environment Variables

Create production `.env` with **all required values**:

```env
# Application
APP_VERSION=2.0.0
APP_NAME=FlowVest AI
APP_URL=https://your-domain.com
DEBUG=false
CORS_ORIGINS=https://your-domain.com

# Database (Cloud SQL connection string)
DATABASE_URL=postgresql://flowvest:PASSWORD@HOST:5432/flowvest?sslmode=require

# Redis (Cloud Memorystore connection string)
REDIS_URL=rediss://HOST:6379/0
CELERY_BROKER_URL=rediss://HOST:6379/0
CELERY_RESULT_BACKEND=rediss://HOST:6379/1

# Celery
CELERY_TASK_SOFT_TIME_LIMIT=300
CELERY_TASK_TIME_LIMIT=360

# Firebase
FIREBASE_PROJECT_ID=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=/app/service-account.json
AUTH_DISABLED=false  # MUST be false in production!

# OpenRouter
OPENROUTER_API_KEY=sk-or-v1-xxxxx
OPENROUTER_MODEL=deepseek/deepseek-chat-v3-0324
OPENROUTER_FALLBACK_MODEL=openai/gpt-4o-mini
LLM_MAX_TOKENS_ANALYSIS=220
LLM_MAX_TOKENS_ADVISOR=280
LLM_TEMPERATURE_ANALYSIS=0.4
LLM_TEMPERATURE_ADVISOR=0.45
LLM_CACHE_TTL=600

# Market Data
ALPHA_VANTAGE_API_KEY=your-av-key
FMP_API_KEY=your-fmp-key
MARKET_CACHE_TTL=300

# Rate Limiting
RATE_LIMIT_PER_MINUTE=10
RATE_LIMIT_GLOBAL_PER_MINUTE=200

# Versioning
MODEL_VERSION=v2
PROMPT_VERSION=v1
ALLOCATION_VERSION=v1

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### 2. Security Hardening

- [ ] `AUTH_DISABLED=false` (CRITICAL!)
- [ ] CORS locked to production domain
- [ ] Database password rotated from default
- [ ] Redis requires authentication
- [ ] SSL/TLS enabled for all connections
- [ ] Secrets stored in Secret Manager / AWS Secrets Manager
- [ ] Firewall rules restrict database access to app only

### 3. Database Migrations

```bash
# Run Alembic migrations
alembic upgrade head

# Verify tables created
psql $DATABASE_URL -c "\dt"
```

### 4. Build Frontend

```bash
npm install
npm run build
# Output: dist/index.html (~290KB)
```

---

## 🚀 Deployment: Google Cloud Run (Step-by-Step)

### 1. Enable APIs

```bash
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable sqladmin.googleapis.com
gcloud services enable redis.googleapis.com
```

### 2. Create Cloud SQL (PostgreSQL)

```bash
gcloud sql instances create flowvest-postgres \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1 \
  --root-password=YOUR_ROOT_PASSWORD

gcloud sql databases create flowvest --instance=flowvest-postgres

gcloud sql users create flowvest \
  --instance=flowvest-postgres \
  --password=YOUR_USER_PASSWORD
```

### 3. Create Cloud Memorystore (Redis)

```bash
gcloud redis instances create flowvest-redis \
  --region=us-central1 \
  --tier=standard \
  --memory-size=1
```

### 4. Build and Deploy Backend

```bash
# Build container
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/flowvest-backend

# Deploy to Cloud Run
gcloud run deploy flowvest-backend \
  --image gcr.io/YOUR_PROJECT_ID/flowvest-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars DATABASE_URL=postgresql://...,REDIS_URL=rediss://... \
  --set-secrets GOOGLE_APPLICATION_CREDENTIALS=firebase-sa:latest
```

### 5. Deploy Celery Worker

```bash
gcloud run deploy flowvest-celery \
  --image gcr.io/YOUR_PROJECT_ID/flowvest-backend \
  --platform managed \
  --region us-central1 \
  --command="celery" \
  --args="-A,backend.tasks.celery_app,worker,--loglevel=info,--concurrency=4" \
  --set-env-vars DATABASE_URL=postgresql://...,REDIS_URL=rediss://... \
  --set-secrets GOOGLE_APPLICATION_CREDENTIALS=firebase-sa:latest \
  --min-instances=1  # Keep at least 1 worker warm
```

### 6. Deploy Frontend

**Option A: Firebase Hosting**

```bash
npm run build
firebase deploy --only hosting
```

**Option B: Cloud Run**

```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/flowvest-frontend
gcloud run deploy flowvest-frontend \
  --image gcr.io/YOUR_PROJECT_ID/flowvest-frontend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### 7. Configure Custom Domain

```bash
gcloud run services update-traffic flowvest-backend \
  --to-latest=100 \
  --update-labels=domain-mapped=true

# Follow Cloud Run custom domain setup wizard
```

---

## 📊 Monitoring & Alerting

### 1. Cloud Monitoring Dashboards

Create dashboards for:
- Request latency (p50, p95, p99)
- Error rates (4xx, 5xx)
- Celery task queue depth
- Celery task success/failure rates
- Database connection pool usage
- Redis memory usage
- LLM API costs

### 2. Alerting Policies

Set up alerts for:
- Error rate > 5% over 5 minutes
- Celery task failure rate > 10% over 10 minutes
- Database CPU > 80% over 5 minutes
- Redis memory > 80%
- LLM daily cost > $5
- Backend response time p99 > 2s

### 3. Logging

All logs are JSON-formatted and shipped to Cloud Logging.

Query examples:

```
# All errors
resource.type="cloud_run_revision"
severity>=ERROR

# Celery task failures
resource.type="cloud_run_revision"
jsonPayload.task_name="backend.tasks.portfolio_tasks.run_portfolio_pipeline"
jsonPayload.status="FAILURE"

# High LLM costs
resource.type="cloud_run_revision"
jsonPayload.event="LLM call OK"
```

---

## 🔐 Security Best Practices

### 1. Secrets Management

**DO NOT** store secrets in environment variables directly. Use Secret Manager:

```bash
# Store secret
gcloud secrets create openrouter-api-key --data-file=openrouter-key.txt

# Grant Cloud Run access
gcloud secrets add-iam-policy-binding openrouter-api-key \
  --member="serviceAccount:YOUR_SERVICE_ACCOUNT" \
  --role="roles/secretmanager.secretAccessor"

# Mount in Cloud Run
gcloud run deploy flowvest-backend \
  --set-secrets OPENROUTER_API_KEY=openrouter-api-key:latest
```

### 2. Network Security

- Enable VPC Service Controls
- Restrict Cloud SQL to private IP only
- Use Cloud Armor for DDoS protection
- Enable Identity-Aware Proxy (IAP) for admin endpoints

### 3. Authentication

- Require Firebase JWT on all protected endpoints
- Enable Firebase App Check for frontend
- Implement rate limiting (already configured)
- Log all authentication failures

---

## 🧪 Post-Deployment Verification

### 1. Health Checks

```bash
curl https://your-domain.com/health
# Expected: {"status":"healthy","database":"online","redis":"online",...}
```

### 2. End-to-End Test

```bash
# Submit portfolio request
curl -X POST https://your-domain.com/portfolio/create \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"budget": 250000, "risk": "Medium", "horizon": "Long"}'

# Poll execution status
curl https://your-domain.com/portfolio/execution/EXECUTION_ID \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN"
```

### 3. Load Test

```bash
# Install k6
brew install k6

# Run load test (100 concurrent users, 5 minutes)
k6 run load-test.js
```

---

## 🆘 Troubleshooting

### Issue: Celery Tasks Not Processing

**Symptoms**: Executions stay in "pending" status forever.

**Solutions**:
1. Check Celery worker logs: `gcloud run services logs read flowvest-celery`
2. Verify Redis connectivity: `redis-cli -h HOST -p 6379 ping`
3. Check worker scale: `gcloud run services describe flowvest-celery`
4. Ensure `--min-instances=1` is set

### Issue: Database Connection Errors

**Symptoms**: `could not connect to server` errors.

**Solutions**:
1. Verify Cloud SQL instance is running
2. Check connection string (host, port, credentials)
3. Ensure Cloud Run service account has Cloud SQL Client role
4. Check Cloud SQL connection limits

### Issue: High LLM Costs

**Symptoms**: LLM costs exceeding budget.

**Solutions**:
1. Check `LLM_CACHE_TTL` is set (default 600s)
2. Verify fallback model is cheaper
3. Add stricter rate limits
4. Review prompt efficiency (shorter prompts = fewer tokens)

---

## 📈 Scaling

### Horizontal Scaling

**Backend (Cloud Run)**:
```bash
gcloud run services update flowvest-backend \
  --min-instances=0 \
  --max-instances=10 \
  --concurrency=80
```

**Celery Workers**:
```bash
gcloud run services update flowvest-celery \
  --min-instances=2 \
  --max-instances=20
```

### Database Scaling

- **Vertical**: Upgrade Cloud SQL tier (`db-f1-micro` → `db-g1-small` → `db-n1-standard-1`)
- **Read Replicas**: Add read replicas for read-heavy workloads
- **Connection Pooling**: Use PgBouncer for high-concurrency scenarios

### Redis Scaling

- **Vertical**: Increase Cloud Memorystore memory (1GB → 2GB → 4GB)
- **Sharding**: Implement Redis Cluster for very high throughput

---

## 💰 Cost Optimization

1. **Use Preemptible VMs** for Celery workers (60-90% savings)
2. **Enable Cloud SQL Auto-Scaling** (scale down during low traffic)
3. **Set Aggressive LLM Cache TTL** (reduce API calls)
4. **Use Committed Use Discounts** for steady-state workloads
5. **Monitor with Cost Explorer** and set budget alerts

---

## 📞 Support

- **Documentation**: `README.md`, `PRD.md`, `ScratchPad.md`
- **Issues**: GitHub Issues tab
- **Emergencies**: Contact on-call engineer via PagerDuty

---

**Last Updated**: May 2026  
**Maintainer**: FlowVest AI DevOps Team
