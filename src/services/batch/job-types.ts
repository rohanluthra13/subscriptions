export type JobType = 'initial_sync' | 'incremental_sync' | 'manual_sync';
export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface JobDefinition {
  type: JobType;
  name: string;
  description: string;
  defaultTimeout: number;
  priority: number;
  retryable: boolean;
  maxRetries: number;
}

export const JOB_DEFINITIONS: Record<JobType, JobDefinition> = {
  initial_sync: {
    type: 'initial_sync',
    name: 'Initial Onboarding Sync',
    description: 'Process 6 months of historical emails during first-time setup',
    defaultTimeout: 30 * 60 * 1000, // 30 minutes
    priority: 1,
    retryable: true,
    maxRetries: 2
  },
  incremental_sync: {
    type: 'incremental_sync', 
    name: 'Daily Incremental Sync',
    description: 'Process new emails since last sync (daily cron job)',
    defaultTimeout: 10 * 60 * 1000, // 10 minutes
    priority: 2,
    retryable: true,
    maxRetries: 3
  },
  manual_sync: {
    type: 'manual_sync',
    name: 'Manual Refresh',
    description: 'User-triggered sync to check for new emails immediately',
    defaultTimeout: 5 * 60 * 1000, // 5 minutes
    priority: 3,
    retryable: false,
    maxRetries: 1
  }
};

export interface JobMetrics {
  jobId: string;
  jobType: JobType;
  connectionId: string;
  
  startedAt: Date;
  completedAt?: Date;
  processingTimeMs: number;
  
  totalEmails: number;
  processedEmails: number;
  subscriptionsFound: number;
  errorsCount: number;
  
  costMetrics?: {
    llmCalls: number;
    totalCost: number;
    avgCostPerEmail: number;
  };
  
  performanceMetrics?: {
    emailsPerSecond: number;
    avgProcessingTimePerEmail: number;
    peakMemoryUsage: number;
  };
}

export class JobValidator {
  static validateJobType(jobType: string): JobType {
    if (!Object.keys(JOB_DEFINITIONS).includes(jobType)) {
      throw new Error(`Invalid job type: ${jobType}`);
    }
    return jobType as JobType;
  }

  static validateJobStatus(status: string): JobStatus {
    const validStatuses: JobStatus[] = ['pending', 'running', 'completed', 'failed', 'cancelled'];
    if (!validStatuses.includes(status as JobStatus)) {
      throw new Error(`Invalid job status: ${status}`);
    }
    return status as JobStatus;
  }

  static canRetryJob(jobType: JobType, currentRetries: number): boolean {
    const definition = JOB_DEFINITIONS[jobType];
    return definition.retryable && currentRetries < definition.maxRetries;
  }

  static getJobTimeout(jobType: JobType): number {
    return JOB_DEFINITIONS[jobType].defaultTimeout;
  }

  static getJobPriority(jobType: JobType): number {
    return JOB_DEFINITIONS[jobType].priority;
  }
}

export interface JobExecutionContext {
  jobId: string;
  connectionId: string;
  jobType: JobType;
  startedAt: Date;
  timeout: number;
  
  onProgress?: (progress: {
    processed: number;
    total: number;
    subscriptionsFound: number;
    errors: number;
  }) => void;
  
  onError?: (error: Error, emailId?: string) => void;
  onComplete?: (metrics: JobMetrics) => void;
}