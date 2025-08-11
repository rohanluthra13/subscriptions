ALTER TABLE "subscriptions" ADD COLUMN "renewal_type" text DEFAULT 'auto_renew';--> statement-breakpoint
CREATE INDEX "idx_subscriptions_renewal_type" ON "subscriptions" USING btree ("renewal_type");