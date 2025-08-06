export { SyncOrchestrator } from './sync-orchestrator';
export { ProgressTracker } from './progress-tracker';
export { 
  DeduplicationService, 
  EmailFilter,
  EmailValidationStep,
  FilteringStep,
  SubscriptionDetectionStep
} from './pipeline-steps';

export type { 
  ProcessingStats, 
  SyncResult
} from './sync-orchestrator';

export type {
  ProgressUpdate,
  ProgressCallback  
} from './progress-tracker';

export type {
  ProcessingStep,
  ProcessingContext,
  ProcessingStepResult,
  DeduplicationOptions
} from './pipeline-steps';