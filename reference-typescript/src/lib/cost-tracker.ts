import { CostMetrics } from '@/lib/types/llm';

export interface CostTrackingEntry {
  timestamp: Date;
  operation: 'subscription_detection' | 'quick_check';
  metrics: CostMetrics;
  emailId?: string;
  success: boolean;
  errorMessage?: string;
}

export class CostTracker {
  private entries: CostTrackingEntry[] = [];
  private sessionStart: Date;

  constructor() {
    this.sessionStart = new Date();
  }

  track(
    operation: CostTrackingEntry['operation'],
    metrics: CostMetrics,
    success: boolean,
    emailId?: string,
    errorMessage?: string
  ): void {
    this.entries.push({
      timestamp: new Date(),
      operation,
      metrics,
      emailId,
      success,
      errorMessage,
    });
  }

  getSessionStats(): {
    totalCost: number;
    totalTokens: number;
    emailsProcessed: number;
    successRate: number;
    avgCostPerEmail: number;
    costBreakdown: Record<string, { cost: number; count: number }>;
  } {
    const totalCost = this.entries.reduce((sum, entry) => sum + entry.metrics.estimatedCost, 0);
    const totalTokens = this.entries.reduce((sum, entry) => sum + entry.metrics.totalTokens, 0);
    const emailsProcessed = this.entries.length;
    const successfulEntries = this.entries.filter(entry => entry.success);
    
    const costBreakdown: Record<string, { cost: number; count: number }> = {};
    this.entries.forEach(entry => {
      if (!costBreakdown[entry.operation]) {
        costBreakdown[entry.operation] = { cost: 0, count: 0 };
      }
      costBreakdown[entry.operation].cost += entry.metrics.estimatedCost;
      costBreakdown[entry.operation].count++;
    });

    return {
      totalCost,
      totalTokens,
      emailsProcessed,
      successRate: emailsProcessed > 0 ? successfulEntries.length / emailsProcessed : 0,
      avgCostPerEmail: emailsProcessed > 0 ? totalCost / emailsProcessed : 0,
      costBreakdown,
    };
  }

  getDailyProjection(): number {
    const sessionDuration = Date.now() - this.sessionStart.getTime();
    const hourlyRate = this.getSessionStats().totalCost / (sessionDuration / (1000 * 60 * 60));
    return hourlyRate * 24;
  }

  getMonthlyProjection(emailsPerDay: number = 50): number {
    const avgCostPerEmail = this.getSessionStats().avgCostPerEmail;
    return avgCostPerEmail * emailsPerDay * 30;
  }

  logCostWarning(): void {
    const stats = this.getSessionStats();
    const target = 0.003;
    
    if (stats.avgCostPerEmail > target) {
      console.warn(`Cost per email (${stats.avgCostPerEmail.toFixed(6)}) exceeds target (${target})`);
    }
    
    const monthlyProjection = this.getMonthlyProjection();
    if (monthlyProjection > 1.5) {
      console.warn(`Monthly cost projection ($${monthlyProjection.toFixed(2)}) may be high`);
    }
  }

  exportMetrics(): string {
    const stats = this.getSessionStats();
    return JSON.stringify({
      session_start: this.sessionStart.toISOString(),
      session_end: new Date().toISOString(),
      ...stats,
      entries: this.entries,
    }, null, 2);
  }

  reset(): void {
    this.entries = [];
    this.sessionStart = new Date();
  }
}