import type { EmailData } from '../../lib/gmail/types';
import type { SubscriptionData } from '../llm/types';
import type { Subscription } from '../../lib/db/schema';

export interface DeduplicationOptions {
  vendorNameSimilarity?: number;
  emailSimilarity?: number;
  amountTolerance?: number;
}

export class DeduplicationService {
  private readonly DEFAULT_OPTIONS: Required<DeduplicationOptions> = {
    vendorNameSimilarity: 0.8,
    emailSimilarity: 0.9,
    amountTolerance: 0.01
  };

  isDuplicate(
    newSubscription: SubscriptionData,
    existing: Subscription,
    options: DeduplicationOptions = {}
  ): boolean {
    const opts = { ...this.DEFAULT_OPTIONS, ...options };

    if (this.isExactMatch(newSubscription, existing)) {
      return true;
    }

    if (this.isFuzzyMatch(newSubscription, existing, opts)) {
      return true;
    }

    return false;
  }

  private isExactMatch(newSub: SubscriptionData, existing: Subscription): boolean {
    return (
      this.normalizeVendorName(newSub.vendor_name) === 
      this.normalizeVendorName(existing.vendorName) &&
      this.normalizeEmail(newSub.vendor_email || '') === 
      this.normalizeEmail(existing.vendorEmail || '')
    );
  }

  private isFuzzyMatch(
    newSub: SubscriptionData,
    existing: Subscription,
    options: Required<DeduplicationOptions>
  ): boolean {
    const vendorSimilarity = this.calculateStringSimilarity(
      this.normalizeVendorName(newSub.vendor_name),
      this.normalizeVendorName(existing.vendorName)
    );

    if (vendorSimilarity < options.vendorNameSimilarity) {
      return false;
    }

    const newEmail = this.normalizeEmail(newSub.vendor_email || '');
    const existingEmail = this.normalizeEmail(existing.vendorEmail || '');
    
    if (newEmail && existingEmail) {
      const emailSimilarity = this.calculateStringSimilarity(newEmail, existingEmail);
      if (emailSimilarity < options.emailSimilarity) {
        return false;
      }
    }

    if (newSub.amount && existing.amount) {
      const amountDiff = Math.abs(
        parseFloat(newSub.amount.toString()) - parseFloat(existing.amount.toString())
      );
      if (amountDiff > options.amountTolerance) {
        return false;
      }
    }

    return true;
  }

  private normalizeVendorName(name: string): string {
    return name
      .toLowerCase()
      .replace(/[^\w\s]/g, '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  private normalizeEmail(email: string): string {
    return email.toLowerCase().trim();
  }

  private calculateStringSimilarity(str1: string, str2: string): number {
    if (str1 === str2) return 1.0;
    if (str1.length === 0 || str2.length === 0) return 0.0;

    const longer = str1.length > str2.length ? str1 : str2;
    const shorter = str1.length > str2.length ? str2 : str1;

    if (longer.length === 0) return 1.0;

    const editDistance = this.levenshteinDistance(longer, shorter);
    return (longer.length - editDistance) / longer.length;
  }

  private levenshteinDistance(str1: string, str2: string): number {
    const matrix = Array(str2.length + 1).fill(null).map(() => Array(str1.length + 1).fill(null));

    for (let i = 0; i <= str1.length; i++) matrix[0][i] = i;
    for (let j = 0; j <= str2.length; j++) matrix[j][0] = j;

    for (let j = 1; j <= str2.length; j++) {
      for (let i = 1; i <= str1.length; i++) {
        const indicator = str1[i - 1] === str2[j - 1] ? 0 : 1;
        matrix[j][i] = Math.min(
          matrix[j][i - 1] + 1,
          matrix[j - 1][i] + 1,
          matrix[j - 1][i - 1] + indicator
        );
      }
    }

    return matrix[str2.length][str1.length];
  }
}

export class EmailFilter {
  static shouldProcessEmail(email: EmailData): boolean {
    const subject = email.subject.toLowerCase();
    const sender = email.sender.toLowerCase();
    const body = email.body.toLowerCase().substring(0, 500);
    
    const skipPatterns = [
      'unsubscribe successful',
      'unsubscribed',
      'newsletter',
      'promotional',
      'sale ends',
      'limited time offer',
      'deal of the day',
      'flash sale',
      'social media',
      'calendar invite',
      'meeting invitation',
      'password reset',
      'verify your email',
      'confirm your account',
      'shipping confirmation',
      'order shipped',
      'delivery update',
      'package delivered',
      'tracking number',
      'out for delivery'
    ];
    
    const combinedText = `${subject} ${sender} ${body}`;
    if (skipPatterns.some(pattern => combinedText.includes(pattern))) {
      return false;
    }
    
    const priorityPatterns = [
      'subscription',
      'billing',
      'invoice',
      'receipt',
      'payment',
      'renewal',
      'charged',
      'auto-pay',
      'membership',
      'recurring',
      'monthly fee',
      'annual fee',
      'your plan',
      'subscription plan',
      'payment method',
      'next billing',
      'billing cycle',
      'renews on',
      'expires on',
      'trial ending',
      'free trial',
      'credit card',
      'payment due',
      'amount due'
    ];
    
    return priorityPatterns.some(pattern => combinedText.includes(pattern));
  }

  static getFilterStats(emails: EmailData[]): {
    total: number;
    filtered: number;
    processed: number;
    filterRatio: number;
  } {
    const filtered = emails.filter(email => this.shouldProcessEmail(email));
    
    return {
      total: emails.length,
      filtered: emails.length - filtered.length,
      processed: filtered.length,
      filterRatio: emails.length > 0 ? filtered.length / emails.length : 0
    };
  }
}

export interface ProcessingStep {
  name: string;
  execute(email: EmailData, context: ProcessingContext): Promise<ProcessingStepResult>;
}

export interface ProcessingContext {
  connectionId: string;
  jobId: string;
  stats: {
    processed: number;
    subscriptionsFound: number;
    errors: number;
  };
}

export interface ProcessingStepResult {
  success: boolean;
  subscription?: SubscriptionData;
  error?: string;
  skipReason?: string;
}

export class EmailValidationStep implements ProcessingStep {
  name = 'email-validation';

  async execute(email: EmailData): Promise<ProcessingStepResult> {
    if (!email.subject || !email.sender) {
      return {
        success: false,
        error: 'Missing required email fields (subject or sender)'
      };
    }

    if (email.body.length < 10) {
      return {
        success: false,
        skipReason: 'Email body too short to contain subscription information'
      };
    }

    return { success: true };
  }
}

export class FilteringStep implements ProcessingStep {
  name = 'email-filtering';

  async execute(email: EmailData): Promise<ProcessingStepResult> {
    if (!EmailFilter.shouldProcessEmail(email)) {
      return {
        success: false,
        skipReason: 'Email filtered out - unlikely to contain subscription information'
      };
    }

    return { success: true };
  }
}

export class SubscriptionDetectionStep implements ProcessingStep {
  name = 'subscription-detection';

  constructor(private detector: any) {}

  async execute(email: EmailData): Promise<ProcessingStepResult> {
    try {
      const result = await this.detector.detectSubscription(email);
      
      if (result.error) {
        return {
          success: false,
          error: result.error
        };
      }

      if (!result.subscription) {
        return {
          success: false,
          skipReason: 'No subscription detected in email'
        };
      }

      return {
        success: true,
        subscription: result.subscription
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Subscription detection failed'
      };
    }
  }
}