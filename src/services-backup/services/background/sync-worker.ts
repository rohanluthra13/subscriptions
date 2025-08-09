import { DatabaseService } from '../../lib/db/service';
import { SyncOrchestrator } from '../processing/sync-orchestrator';
import { SubscriptionDetector } from '../llm/subscription-detector';
import type { Connection } from '../../lib/db/schema';

export class SyncWorker {
  private syncOrchestrator: SyncOrchestrator;

  constructor(private database: DatabaseService) {
    const subscriptionDetector = new SubscriptionDetector();
    this.syncOrchestrator = new SyncOrchestrator(database, subscriptionDetector);
  }

  async executeDailySyncForAllConnections(): Promise<void> {
    console.log('Starting daily sync for all active connections...');
    
    try {
      const activeConnections = await this.getActiveConnections();
      
      if (activeConnections.length === 0) {
        console.log('No active connections found for daily sync');
        return;
      }

      console.log(`Found ${activeConnections.length} active connections to sync`);

      const results = await Promise.allSettled(
        activeConnections.map(connection => this.processSingleConnection(connection))
      );

      const successful = results.filter(r => r.status === 'fulfilled').length;
      const failed = results.filter(r => r.status === 'rejected').length;

      console.log(`Daily sync completed: ${successful} successful, ${failed} failed`);

      if (failed > 0) {
        const failedConnections = results
          .map((result, index) => ({ result, connection: activeConnections[index] }))
          .filter(({ result }) => result.status === 'rejected')
          .map(({ result, connection }) => ({
            connectionId: connection.id,
            error: result.status === 'rejected' ? result.reason : 'Unknown error'
          }));

        console.error('Failed connections:', failedConnections);
        await this.logDailySyncFailures(failedConnections);
      }

    } catch (error) {
      console.error('Daily sync failed:', error);
      throw error;
    }
  }

  private async getActiveConnections(): Promise<Connection[]> {
    // Get all active connections
    const allConnections = await this.database.getAllActiveConnections();
    
    // Filter out connections that already have active sync jobs
    const availableConnections = [];
    
    for (const connection of allConnections) {
      const hasActiveJob = await this.syncOrchestrator.isSyncInProgress(connection.id);
      if (!hasActiveJob) {
        availableConnections.push(connection);
      }
    }

    return availableConnections;
  }

  private async processSingleConnection(connection: Connection): Promise<void> {
    console.log(`Processing daily sync for connection: ${connection.email}`);
    
    try {
      const result = await this.syncOrchestrator.processDailySync(connection);
      
      console.log(`✓ Connection ${connection.email} sync completed:`, {
        jobId: result.jobId,
        subscriptionsFound: result.stats.subscriptionsFound,
        processed: result.stats.processed,
        errors: result.stats.errors,
        timeMs: result.processingTimeMs
      });
      
    } catch (error) {
      console.error(`✗ Connection ${connection.email} sync failed:`, error);
      throw error;
    }
  }

  private async logDailySyncFailures(failures: Array<{ connectionId: string; error: any }>): Promise<void> {
    // Log failures for monitoring and alerting
    for (const failure of failures) {
      console.error(`Daily sync failure - Connection: ${failure.connectionId}, Error: ${failure.error}`);
      
      // In a production environment, this could send alerts via:
      // - Email notifications
      // - Slack webhooks
      // - Error tracking services (Sentry)
      // - Monitoring systems (DataDog, etc.)
    }
  }

  // For testing and manual triggers
  async executeSingleConnectionSync(connectionId: string): Promise<void> {
    const connection = await this.database.getConnectionById(connectionId);
    if (!connection) {
      throw new Error(`Connection ${connectionId} not found`);
    }

    if (!connection.isActive) {
      throw new Error(`Connection ${connectionId} is not active`);
    }

    await this.processSingleConnection(connection);
  }

  async getWorkerStatus(): Promise<{
    activeConnections: number;
    ongoingSyncs: number;
    lastDailySyncAt?: Date;
  }> {
    const activeConnections = await this.getActiveConnections();
    const allConnections = await this.database.getAllActiveConnections();
    
    const ongoingSyncs = allConnections.length - activeConnections.length;

    return {
      activeConnections: activeConnections.length,
      ongoingSyncs,
      lastDailySyncAt: undefined // Could track this in database if needed
    };
  }
}