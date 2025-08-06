import { eq, and, desc, sql, lt, asc } from 'drizzle-orm';
import { db } from './index';
import { 
  users, 
  connections, 
  subscriptions, 
  processedEmails, 
  syncJobs,
  type Connection,
  type NewConnection,
  type Subscription,
  type NewSubscription,
  type NewProcessedEmail,
  type NewSyncJob
} from './schema';

/**
 * Database service class for subscription tracker
 * Provides abstraction layer over Drizzle ORM operations
 */
export class DatabaseService {
  
  // Transaction support
  async withTransaction<T>(callback: (tx: any) => Promise<T>): Promise<T> {
    return await db.transaction(callback);
  }
  
  // Connection operations
  async createConnection(data: NewConnection): Promise<Connection> {
    const [connection] = await db.insert(connections)
      .values(data)
      .returning();
    return connection;
  }

  async getActiveConnection(userId: string = '1'): Promise<Connection | null> {
    const [connection] = await db.select()
      .from(connections)
      .where(and(
        eq(connections.userId, userId),
        eq(connections.isActive, true)
      ))
      .limit(1);
    return connection || null;
  }

  async updateConnectionLastSync(connectionId: string): Promise<void> {
    await db.update(connections)
      .set({ 
        lastSyncAt: sql`NOW()`,
        updatedAt: sql`NOW()`
      })
      .where(eq(connections.id, connectionId));
  }

  // Subscription operations
  async saveSubscription(data: NewSubscription): Promise<Subscription> {
    const [subscription] = await db.insert(subscriptions)
      .values(data)
      .returning();
    return subscription;
  }

  async findDuplicateSubscription(
    vendorName: string, 
    vendorEmail: string, 
    userId: string = '1'
  ): Promise<Subscription | null> {
    const [existing] = await db.select()
      .from(subscriptions)
      .where(and(
        eq(subscriptions.userId, userId),
        eq(subscriptions.vendorName, vendorName),
        eq(subscriptions.vendorEmail, vendorEmail)
      ))
      .limit(1);
    return existing || null;
  }

  async getSubscriptions(filters: {
    userId?: string;
    status?: string;
    category?: string;
    search?: string;
    sort?: 'amount' | 'date' | 'name';
    order?: 'asc' | 'desc';
    limit?: number;
    offset?: number;
  } = {}): Promise<{ items: Subscription[]; total: number }> {
    const { 
      userId = '1', 
      status, 
      category, 
      search, 
      sort = 'date', 
      order = 'desc',
      limit = 20,
      offset = 0 
    } = filters;

    // Build where conditions
    const conditions = [eq(subscriptions.userId, userId)];
    
    if (status) {
      conditions.push(eq(subscriptions.status, status as any));
    }
    
    if (category) {
      conditions.push(eq(subscriptions.category, category));
    }
    
    if (search) {
      conditions.push(sql`${subscriptions.vendorName} ILIKE ${'%' + search + '%'}`);
    }
    
    // Apply sorting
    let orderBy;
    if (sort === 'amount') {
      orderBy = order === 'asc' ? asc(subscriptions.amount) : desc(subscriptions.amount);
    } else if (sort === 'name') {
      orderBy = order === 'asc' ? asc(subscriptions.vendorName) : desc(subscriptions.vendorName);
    } else {
      orderBy = order === 'asc' ? asc(subscriptions.detectedAt) : desc(subscriptions.detectedAt);
    }
    
    // Get total count
    const [{ count }] = await db.select({ count: sql<number>`count(*)` })
      .from(subscriptions)
      .where(and(...conditions));
    
    // Get items with pagination
    const items = await db.select()
      .from(subscriptions)
      .where(and(...conditions))
      .orderBy(orderBy)
      .limit(limit)
      .offset(offset);
    
    return { items, total: count };
  }

  async getSubscriptionById(subscriptionId: string, userId: string = '1'): Promise<Subscription | null> {
    const [subscription] = await db.select()
      .from(subscriptions)
      .where(and(
        eq(subscriptions.id, subscriptionId),
        eq(subscriptions.userId, userId)
      ))
      .limit(1);
    return subscription || null;
  }

  async updateSubscription(subscriptionId: string, data: Partial<NewSubscription>): Promise<Subscription> {
    const [updated] = await db.update(subscriptions)
      .set({ ...data, updatedAt: sql`NOW()` })
      .where(eq(subscriptions.id, subscriptionId))
      .returning();
    return updated;
  }

  async deleteSubscription(subscriptionId: string): Promise<void> {
    await db.delete(subscriptions)
      .where(eq(subscriptions.id, subscriptionId));
  }

  async batchSaveSubscriptions(subscriptionData: NewSubscription[]): Promise<Subscription[]> {
    return await this.withTransaction(async (tx) => {
      const results: Subscription[] = [];
      for (const subscription of subscriptionData) {
        const [saved] = await tx.insert(subscriptions)
          .values(subscription)
          .returning();
        results.push(saved);
      }
      return results;
    });
  }

  // Email processing operations
  async isEmailProcessed(gmailMessageId: string): Promise<boolean> {
    const [result] = await db.select({ count: sql<number>`count(*)` })
      .from(processedEmails)
      .where(eq(processedEmails.gmailMessageId, gmailMessageId));
    return result.count > 0;
  }

  async logProcessedEmail(data: NewProcessedEmail): Promise<void> {
    await db.insert(processedEmails)
      .values(data)
      .onConflictDoNothing();
  }

  // Sync job operations
  async createSyncJob(data: NewSyncJob): Promise<string> {
    const [job] = await db.insert(syncJobs)
      .values(data)
      .returning({ id: syncJobs.id });
    return job.id;
  }

  async updateSyncJobProgress(
    jobId: string, 
    progress: {
      processedEmails: number;
      subscriptionsFound: number;
      errorsCount: number;
    }
  ): Promise<void> {
    await db.update(syncJobs)
      .set({
        processedEmails: progress.processedEmails,
        subscriptionsFound: progress.subscriptionsFound,
        errorsCount: progress.errorsCount,
      })
      .where(eq(syncJobs.id, jobId));
  }

  async completeSyncJob(jobId: string, success: boolean = true): Promise<void> {
    await db.update(syncJobs)
      .set({
        status: success ? 'completed' : 'failed',
        completedAt: sql`NOW()`,
      })
      .where(eq(syncJobs.id, jobId));
  }

  async getSyncJobStatus(jobId: string) {
    const [job] = await db.select()
      .from(syncJobs)
      .where(eq(syncJobs.id, jobId))
      .limit(1);
    return job || null;
  }

  async getSyncJob(jobId: string) {
    const [job] = await db.select()
      .from(syncJobs)
      .where(eq(syncJobs.id, jobId))
      .limit(1);
    return job || null;
  }

  // Background worker support
  async getAllActiveConnections(): Promise<Connection[]> {
    return await db.select()
      .from(connections)
      .where(eq(connections.isActive, true))
      .orderBy(desc(connections.lastSyncAt));
  }

  async getConnectionById(connectionId: string): Promise<Connection | null> {
    const [connection] = await db.select()
      .from(connections)
      .where(eq(connections.id, connectionId))
      .limit(1);
    return connection || null;
  }

  async cleanupOldSyncJobs(daysOld: number): Promise<number> {
    const cutoffDate = new Date(Date.now() - daysOld * 24 * 60 * 60 * 1000);
    
    const result = await db.delete(syncJobs)
      .where(and(
        eq(syncJobs.status, 'completed'),
        lt(syncJobs.completedAt, cutoffDate)
      ))
      .returning({ id: syncJobs.id });

    console.log(`Cleaned up ${result.length} old sync jobs`);
    return result.length;
  }

  // Expose db for complex queries in JobMonitor
  get db() {
    return db;
  }

  // Health check
  async healthCheck(): Promise<boolean> {
    try {
      await db.select({ count: sql<number>`1` }).from(users).limit(1);
      return true;
    } catch (error) {
      console.error('Database health check failed:', error);
      return false;
    }
  }
}