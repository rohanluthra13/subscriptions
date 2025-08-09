import { pgTable, text, timestamp, boolean, integer, decimal, date, index } from 'drizzle-orm/pg-core';
import { sql } from 'drizzle-orm';

// Users table (multi-user foundation, single-user implementation)
export const users = pgTable('users', {
  id: text('id').primaryKey().default(sql`gen_random_uuid()`),
  email: text('email').unique().notNull(),
  name: text('name'),
  createdAt: timestamp('created_at').default(sql`NOW()`),
  updatedAt: timestamp('updated_at').default(sql`NOW()`),
});

// Gmail connections (adapted from Zero)
export const connections = pgTable('connections', {
  id: text('id').primaryKey().default(sql`gen_random_uuid()`),
  userId: text('user_id').notNull().default('1').references(() => users.id, { onDelete: 'cascade' }),
  email: text('email').notNull(),
  accessToken: text('access_token').notNull(),
  refreshToken: text('refresh_token').notNull(),
  tokenExpiry: timestamp('token_expiry').notNull(),
  historyId: text('history_id'), // Gmail history ID for incremental sync
  lastSyncAt: timestamp('last_sync_at'),
  isActive: boolean('is_active').default(true),
  createdAt: timestamp('created_at').default(sql`NOW()`),
  updatedAt: timestamp('updated_at').default(sql`NOW()`),
}, (table) => ({
  userActiveIdx: index('idx_connections_user_active').on(table.userId, table.isActive),
}));

// Detected subscriptions (core business data)
export const subscriptions = pgTable('subscriptions', {
  id: text('id').primaryKey().default(sql`gen_random_uuid()`),
  userId: text('user_id').notNull().default('1').references(() => users.id, { onDelete: 'cascade' }),
  connectionId: text('connection_id').notNull().references(() => connections.id, { onDelete: 'cascade' }),
  
  // Core subscription data
  vendorName: text('vendor_name').notNull(),
  vendorEmail: text('vendor_email'),
  amount: decimal('amount', { precision: 10, scale: 2 }),
  currency: text('currency').default('USD'),
  billingCycle: text('billing_cycle'), // 'monthly', 'yearly', 'weekly', 'one-time'
  
  // Important dates
  nextBillingDate: date('next_billing_date'),
  lastBillingDate: date('last_billing_date'),
  detectedAt: timestamp('detected_at').default(sql`NOW()`),
  
  // Status and confidence
  status: text('status', { enum: ['active', 'inactive', 'paused', 'unknown'] }).default('active'),
  renewalType: text('renewal_type', { enum: ['auto_renew', 'manual_renew', 'cancelled', 'free_tier', 'unknown'] }).default('auto_renew'),
  confidenceScore: decimal('confidence_score', { precision: 3, scale: 2 }), // 0.00 to 1.00
  
  // User modifications
  userVerified: boolean('user_verified').default(false),
  userNotes: text('user_notes'),
  
  // Metadata
  category: text('category'), // 'streaming', 'software', 'news', 'fitness', 'other'
  createdAt: timestamp('created_at').default(sql`NOW()`),
  updatedAt: timestamp('updated_at').default(sql`NOW()`),
}, (table) => ({
  userStatusIdx: index('idx_subscriptions_user_status').on(table.userId, table.status),
  nextBillingIdx: index('idx_subscriptions_next_billing').on(table.nextBillingDate).where(sql`${table.status} = 'active'`),
  renewalTypeIdx: index('idx_subscriptions_renewal_type').on(table.renewalType),
}));

// Email processing log (prevent duplicate processing)
export const processedEmails = pgTable('processed_emails', {
  id: text('id').primaryKey().default(sql`gen_random_uuid()`),
  connectionId: text('connection_id').notNull().references(() => connections.id, { onDelete: 'cascade' }),
  gmailMessageId: text('gmail_message_id').unique().notNull(),
  gmailThreadId: text('gmail_thread_id'),
  subject: text('subject'),
  sender: text('sender'),
  receivedAt: timestamp('received_at'),
  processedAt: timestamp('processed_at').default(sql`NOW()`),
  fetchedAt: timestamp('fetched_at').default(sql`NOW()`), // Added for Phase 1
  subscriptionFound: boolean('subscription_found').default(false),
  subscriptionId: text('subscription_id').references(() => subscriptions.id, { onDelete: 'set null' }),
  confidenceScore: decimal('confidence_score', { precision: 3, scale: 2 }),
  processingError: text('processing_error'),
}, (table) => ({
  connectionIdx: index('idx_processed_emails_connection').on(table.connectionId, table.processedAt),
  gmailIdIdx: index('idx_processed_emails_gmail_id').on(table.gmailMessageId),
}));

// Batch processing jobs (track sync progress)
export const syncJobs = pgTable('sync_jobs', {
  id: text('id').primaryKey().default(sql`gen_random_uuid()`),
  connectionId: text('connection_id').notNull().references(() => connections.id, { onDelete: 'cascade' }),
  jobType: text('job_type').notNull(), // 'initial_sync', 'incremental_sync', 'manual_sync'
  status: text('status').default('running'), // 'running', 'completed', 'failed', 'cancelled'
  
  // Progress tracking
  totalEmails: integer('total_emails').default(0),
  processedEmails: integer('processed_emails').default(0),
  subscriptionsFound: integer('subscriptions_found').default(0),
  errorsCount: integer('errors_count').default(0),
  
  // Metadata
  startedAt: timestamp('started_at').default(sql`NOW()`),
  completedAt: timestamp('completed_at'),
  errorMessage: text('error_message'),
}, (table) => ({
  statusIdx: index('idx_sync_jobs_status').on(table.status, table.startedAt),
}));

// Type exports for use in application code
export type User = typeof users.$inferSelect;
export type NewUser = typeof users.$inferInsert;

export type Connection = typeof connections.$inferSelect;
export type NewConnection = typeof connections.$inferInsert;

export type Subscription = typeof subscriptions.$inferSelect;
export type NewSubscription = typeof subscriptions.$inferInsert;

export type ProcessedEmail = typeof processedEmails.$inferSelect;
export type NewProcessedEmail = typeof processedEmails.$inferInsert;

export type SyncJob = typeof syncJobs.$inferSelect;
export type NewSyncJob = typeof syncJobs.$inferInsert;