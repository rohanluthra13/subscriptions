# Dockerfile for Next.js Subscription Tracker
FROM node:20-alpine AS base

# Install dependencies only when needed
FROM base AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./
RUN npm install --omit=dev

# Rebuild the source code only when needed
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Install all dependencies for build step
RUN npm install

# Generate Drizzle files
RUN npm run db:generate

# Build Next.js app with placeholder env vars for build time
ENV DATABASE_URL=postgresql://build:build@localhost:5432/build
ENV POSTGRES_PASSWORD=build
ENV GOOGLE_CLIENT_ID=build
ENV GOOGLE_CLIENT_SECRET=build
ENV OPENAI_API_KEY=build
ENV API_KEY=build
ENV NEXTAUTH_URL=http://localhost:3000
ENV NEXTAUTH_SECRET=build
ARG NEXT_PUBLIC_API_KEY
ENV NEXT_PUBLIC_API_KEY=$NEXT_PUBLIC_API_KEY
RUN npm run build

# Production image, copy all the files and run next
FROM base AS runner
WORKDIR /app

ENV NODE_ENV production

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy built application
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

# Copy Drizzle files
COPY --from=builder /app/drizzle ./drizzle
COPY --from=builder /app/src/lib/db ./src/lib/db

USER nextjs

EXPOSE 3000

ENV PORT 3000
ENV HOSTNAME "0.0.0.0"

CMD ["node", "server.js"]