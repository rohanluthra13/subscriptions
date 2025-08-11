# Deployment Guide

## Prerequisites

Before deploying, ensure you have:
- [ ] All environment variables configured
- [ ] Database accessible from production
- [ ] Gmail OAuth credentials for production domain
- [ ] OpenAI API key
- [ ] Docker and Docker Compose installed (for Docker deployment)

## Environment Setup

### 1. Create Production Environment File

Create `.env.production`:

```env
# Database (use production database URL)
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Gmail OAuth (update redirect URI for production)
GMAIL_CLIENT_ID=your_production_client_id
GMAIL_CLIENT_SECRET=your_production_client_secret
REDIRECT_URI=https://yourdomain.com/api/auth/gmail/callback

# OpenAI
OPENAI_API_KEY=your_api_key

# Encryption (use a secure 32-character key)
ENCRYPTION_KEY=your_secure_32_character_key_here

# Next.js
NEXT_PUBLIC_APP_URL=https://yourdomain.com

# Node Environment
NODE_ENV=production
```

### 2. Update Gmail OAuth Settings

In Google Cloud Console:
1. Go to APIs & Services > Credentials
2. Edit your OAuth 2.0 Client
3. Add production redirect URI: `https://yourdomain.com/api/auth/gmail/callback`
4. Add production domain to authorized JavaScript origins

## Deployment Methods

### Option 1: Docker Deployment (Recommended)

#### Build and Run

```bash
# Build production image
docker build -t subscription-tracker:latest .

# Run with docker-compose
docker-compose -f docker-compose.prod.yml up -d
```

#### Production Docker Compose

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  app:
    image: subscription-tracker:latest
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
    env_file:
      - .env.production
    depends_on:
      - db
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  db:
    image: postgres:17-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=subscription_tracker
      - POSTGRES_USER=subscription_user
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    restart: unless-stopped

  cron:
    image: subscription-tracker:latest
    command: npm run cron:start
    env_file:
      - .env.production
    depends_on:
      - db
    restart: unless-stopped

volumes:
  postgres_data:
```

### Option 2: Node.js Deployment

```bash
# Install dependencies
npm install --production

# Build Next.js
npm run build

# Run migrations
npm run db:migrate:run

# Start production server
npm start

# Start cron worker (in separate process)
npm run cron:start
```

### Option 3: Platform Deployments

#### Vercel

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel --prod

# Set environment variables in Vercel dashboard
```

#### Railway

```bash
# Install Railway CLI
npm i -g @railway/cli

# Deploy
railway up

# Set environment variables in Railway dashboard
```

## Database Setup

### 1. Create Production Database

```sql
-- Create database
CREATE DATABASE subscription_tracker;

-- Create user
CREATE USER subscription_user WITH PASSWORD 'secure_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE subscription_tracker TO subscription_user;
```

### 2. Run Migrations

```bash
# Set production database URL
export DATABASE_URL="postgresql://user:pass@host:5432/subscription_tracker"

# Run migrations
npm run db:migrate:run

# Verify schema
npm run db:studio
```

## Post-Deployment Steps

### 1. Health Check

```bash
# Check application health
curl https://yourdomain.com/api/health

# Expected response
{"status":"healthy","timestamp":"2024-01-15T10:00:00Z"}
```

### 2. Initial Setup

1. Access the application: `https://yourdomain.com`
2. Connect Gmail account
3. Run initial sync
4. Verify subscriptions are detected

### 3. Configure Monitoring

Set up monitoring for:
- Application uptime
- API response times
- Database connections
- Error rates
- Sync job success rate

### 4. Setup Backups

```bash
# Backup database
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql

# Restore database
psql $DATABASE_URL < backup_20240115.sql
```

### 5. Configure SSL

If using Docker/Node.js deployment, set up SSL with:
- Nginx reverse proxy
- Let's Encrypt SSL certificates
- Cloudflare SSL

Example Nginx config:

```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

## Troubleshooting

### Application Won't Start

```bash
# Check logs
docker-compose logs app

# Common issues:
# - Missing environment variables
# - Database connection failed
# - Port already in use
```

### Database Connection Issues

```bash
# Test connection
psql $DATABASE_URL -c "SELECT 1"

# Check if migrations ran
psql $DATABASE_URL -c "\dt"
```

### Gmail OAuth Not Working

1. Verify redirect URI matches exactly
2. Check OAuth credentials
3. Ensure app is published or in test mode with allowed users

### Sync Not Running

```bash
# Check cron worker
docker-compose logs cron

# Manually trigger sync
curl -X POST https://yourdomain.com/api/sync/manual
```

## Rollback Procedure

If deployment fails:

```bash
# Stop new version
docker-compose down

# Restore previous version
docker run -d subscription-tracker:previous

# Restore database if needed
psql $DATABASE_URL < backup_previous.sql
```

## Security Checklist

- [ ] Environment variables secured
- [ ] Database password strong
- [ ] SSL enabled
- [ ] API rate limiting configured
- [ ] Encryption key unique and secure
- [ ] No debug mode in production
- [ ] Logs don't contain sensitive data
- [ ] Backup encryption enabled

## Performance Optimization

### 1. Database Indexes

Ensure indexes are created:
```sql
-- Check existing indexes
SELECT * FROM pg_indexes WHERE tablename = 'subscriptions';
```

### 2. Caching

Configure Redis for caching (optional):
```yaml
redis:
  image: redis:alpine
  restart: unless-stopped
```

### 3. CDN

Use CDN for static assets:
- Cloudflare
- AWS CloudFront
- Vercel Edge Network

## Maintenance

### Daily
- Check sync jobs are running
- Monitor error logs

### Weekly
- Review subscription detection accuracy
- Check API usage and costs

### Monthly
- Database backup test
- Security updates
- Performance review

## Commands Reference

```bash
# Start production
docker-compose -f docker-compose.prod.yml up -d

# Stop production
docker-compose -f docker-compose.prod.yml down

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Restart services
docker-compose -f docker-compose.prod.yml restart

# Database backup
docker exec -t postgres_container pg_dumpall -c -U subscription_user > backup.sql

# Update application
git pull
docker build -t subscription-tracker:latest .
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose -f docker-compose.prod.yml ps
```