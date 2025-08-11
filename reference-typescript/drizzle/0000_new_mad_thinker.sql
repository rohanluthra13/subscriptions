CREATE TABLE "connections" (
	"id" text PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"user_id" text DEFAULT '1' NOT NULL,
	"email" text NOT NULL,
	"access_token" text NOT NULL,
	"refresh_token" text NOT NULL,
	"token_expiry" timestamp NOT NULL,
	"history_id" text,
	"last_sync_at" timestamp,
	"is_active" boolean DEFAULT true,
	"created_at" timestamp DEFAULT NOW(),
	"updated_at" timestamp DEFAULT NOW()
);
--> statement-breakpoint
CREATE TABLE "processed_emails" (
	"id" text PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"connection_id" text NOT NULL,
	"gmail_message_id" text NOT NULL,
	"gmail_thread_id" text,
	"subject" text,
	"sender" text,
	"received_at" timestamp,
	"processed_at" timestamp DEFAULT NOW(),
	"subscription_found" boolean DEFAULT false,
	"subscription_id" text,
	"confidence_score" numeric(3, 2),
	"processing_error" text,
	CONSTRAINT "processed_emails_gmail_message_id_unique" UNIQUE("gmail_message_id")
);
--> statement-breakpoint
CREATE TABLE "subscriptions" (
	"id" text PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"user_id" text DEFAULT '1' NOT NULL,
	"connection_id" text NOT NULL,
	"vendor_name" text NOT NULL,
	"vendor_email" text,
	"amount" numeric(10, 2),
	"currency" text DEFAULT 'USD',
	"billing_cycle" text,
	"next_billing_date" date,
	"last_billing_date" date,
	"detected_at" timestamp DEFAULT NOW(),
	"status" text DEFAULT 'active',
	"confidence_score" numeric(3, 2),
	"user_verified" boolean DEFAULT false,
	"user_notes" text,
	"category" text,
	"created_at" timestamp DEFAULT NOW(),
	"updated_at" timestamp DEFAULT NOW()
);
--> statement-breakpoint
CREATE TABLE "sync_jobs" (
	"id" text PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"connection_id" text NOT NULL,
	"job_type" text NOT NULL,
	"status" text DEFAULT 'running',
	"total_emails" integer DEFAULT 0,
	"processed_emails" integer DEFAULT 0,
	"subscriptions_found" integer DEFAULT 0,
	"errors_count" integer DEFAULT 0,
	"started_at" timestamp DEFAULT NOW(),
	"completed_at" timestamp,
	"error_message" text
);
--> statement-breakpoint
CREATE TABLE "users" (
	"id" text PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"email" text NOT NULL,
	"name" text,
	"created_at" timestamp DEFAULT NOW(),
	"updated_at" timestamp DEFAULT NOW(),
	CONSTRAINT "users_email_unique" UNIQUE("email")
);
--> statement-breakpoint
ALTER TABLE "connections" ADD CONSTRAINT "connections_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "processed_emails" ADD CONSTRAINT "processed_emails_connection_id_connections_id_fk" FOREIGN KEY ("connection_id") REFERENCES "public"."connections"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "processed_emails" ADD CONSTRAINT "processed_emails_subscription_id_subscriptions_id_fk" FOREIGN KEY ("subscription_id") REFERENCES "public"."subscriptions"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "subscriptions" ADD CONSTRAINT "subscriptions_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "subscriptions" ADD CONSTRAINT "subscriptions_connection_id_connections_id_fk" FOREIGN KEY ("connection_id") REFERENCES "public"."connections"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "sync_jobs" ADD CONSTRAINT "sync_jobs_connection_id_connections_id_fk" FOREIGN KEY ("connection_id") REFERENCES "public"."connections"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "idx_connections_user_active" ON "connections" USING btree ("user_id","is_active");--> statement-breakpoint
CREATE INDEX "idx_processed_emails_connection" ON "processed_emails" USING btree ("connection_id","processed_at");--> statement-breakpoint
CREATE INDEX "idx_processed_emails_gmail_id" ON "processed_emails" USING btree ("gmail_message_id");--> statement-breakpoint
CREATE INDEX "idx_subscriptions_user_status" ON "subscriptions" USING btree ("user_id","status");--> statement-breakpoint
CREATE INDEX "idx_subscriptions_next_billing" ON "subscriptions" USING btree ("next_billing_date") WHERE "subscriptions"."status" = 'active';--> statement-breakpoint
CREATE INDEX "idx_sync_jobs_status" ON "sync_jobs" USING btree ("status","started_at");